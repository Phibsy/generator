# backend/app/tasks/content_tasks.py
"""
📝 REELS GENERATOR - Content Generation Tasks
Celery tasks for AI-powered content generation
"""

from celery import shared_task, Task
from celery.exceptions import SoftTimeLimitExceeded
from typing import Dict, Any, List
import logging
import asyncio
from datetime import datetime

from ..services.content_generation import content_service
from ..schemas import ContentGenerationRequest
from ..database import AsyncSessionLocal
from ..models import Project, User
from sqlalchemy import update

logger = logging.getLogger(__name__)

# ============================================================================
# CONTENT GENERATION TASKS
# ============================================================================

@shared_task(
    bind=True,
    name="generate_content",
    queue="content",
    max_retries=3,
    default_retry_delay=60
)
def generate_content_task(
    self: Task,
    project_id: int,
    topic: str,
    target_audience: str,
    video_style: str = "educational",
    duration: int = 60,
    **kwargs
) -> Dict[str, Any]:
    """
    Generate AI-powered content for a project
    
    Priority: Normal
    Queue: content
    Timeout: 5 minutes
    """
    
    task_id = self.request.id
    logger.info(f"Starting content generation task {task_id} for project {project_id}")
    
    try:
        # Update progress
        self.update_progress(task_id, 0, "initializing")
        
        # Create content request
        content_request = ContentGenerationRequest(
            topic=topic,
            target_audience=target_audience,
            video_style=video_style,
            duration=duration,
            tone=kwargs.get("tone", "engaging"),
            include_call_to_action=kwargs.get("include_cta", True)
        )
        
        # Update progress
        self.update_progress(task_id, 20, "generating_script")
        
        # Generate content using async service
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            content = loop.run_until_complete(
                content_service.generate_story(content_request)
            )
            
            # Update progress
            self.update_progress(task_id, 60, "content_generated")
            
            # Save to database
            loop.run_until_complete(
                save_content_to_project(
                    project_id,
                    content.script,
                    content.hashtags,
                    content.suggested_title,
                    content.content_score
                )
            )
            
            # Update progress
            self.update_progress(task_id, 100, "completed")
            
            logger.info(f"Content generation completed for project {project_id}")
            
            return {
                "success": True,
                "project_id": project_id,
                "script_length": len(content.script),
                "hashtag_count": len(content.hashtags),
                "content_score": content.content_score,
                "title": content.suggested_title
            }
            
        finally:
            loop.close()
            
    except SoftTimeLimitExceeded:
        logger.error(f"Content generation task {task_id} timed out")
        self.update_progress(task_id, -1, "timeout")
        raise
        
    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        self.update_progress(task_id, -1, "failed", {"error": str(e)})
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

@shared_task(
    bind=True,
    name="generate_hashtags",
    queue="content",
    max_retries=3
)
def generate_hashtags_task(
    self: Task,
    topic: str,
    target_audience: str,
    platform: str = "instagram"
) -> List[str]:
    """
    Generate optimized hashtags for content
    
    Priority: Low
    Queue: content
    Timeout: 2 minutes
    """
    
    task_id = self.request.id
    
    try:
        self.update_progress(task_id, 0, "generating_hashtags")
        
        # Generate hashtags
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            hashtags = loop.run_until_complete(
                content_service.generate_hashtags(topic, target_audience)
            )
            
            # Platform-specific additions
            if platform == "instagram":
                hashtags = ["reels", "reelsinstagram"] + hashtags
            elif platform == "youtube":
                hashtags = ["shorts", "youtubeshorts"] + hashtags
            elif platform == "tiktok":
                hashtags = ["fyp", "foryou"] + hashtags
            
            self.update_progress(task_id, 100, "completed")
            
            return hashtags[:30]
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Hashtag generation failed: {e}")
        raise self.retry(exc=e)

@shared_task(
    bind=True,
    name="analyze_content_quality",
    queue="content",
    max_retries=2
)
def analyze_content_task(
    self: Task,
    script: str,
    topic: str
) -> Dict[str, Any]:
    """
    Analyze content quality and provide suggestions
    
    Priority: Low
    Queue: content
    Timeout: 2 minutes
    """
    
    task_id = self.request.id
    
    try:
        self.update_progress(task_id, 0, "analyzing")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            analysis = loop.run_until_complete(
                content_service.analyze_content_quality(script, topic)
            )
            
            self.update_progress(task_id, 100, "completed")
            
            return analysis
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Content analysis failed: {e}")
        raise self.retry(exc=e)

@shared_task(
    bind=True,
    name="generate_variations",
    queue="content",
    max_retries=2
)
def generate_variations_task(
    self: Task,
    original_script: str,
    num_variations: int = 3
) -> List[str]:
    """
    Generate script variations for A/B testing
    
    Priority: Normal
    Queue: content
    Timeout: 5 minutes
    """
    
    task_id = self.request.id
    
    try:
        self.update_progress(task_id, 0, "generating_variations")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            variations = loop.run_until_complete(
                content_service.generate_variations(original_script, num_variations)
            )
            
            self.update_progress(task_id, 100, "completed")
            
            return variations
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Variation generation failed: {e}")
        raise self.retry(exc=e)

# ============================================================================
# BATCH CONTENT GENERATION
# ============================================================================

@shared_task(
    bind=True,
    name="batch_generate_content",
    queue="content",
    max_retries=1
)
def batch_generate_content_task(
    self: Task,
    project_ids: List[int],
    user_id: int,
    settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate content for multiple projects
    
    Priority: Low
    Queue: content
    Timeout: 20 minutes
    """
    
    task_id = self.request.id
    results = {
        "successful": [],
        "failed": []
    }
    
    try:
        total = len(project_ids)
        
        for i, project_id in enumerate(project_ids):
            progress = (i / total) * 100
            self.update_progress(
                task_id,
                progress,
                f"processing_project_{project_id}"
            )
            
            try:
                # Submit individual task
                sub_task = generate_content_task.apply_async(
                    args=[project_id],
                    kwargs=settings,
                    priority=3  # Lower priority for batch
                )
                
                results["successful"].append({
                    "project_id": project_id,
                    "task_id": sub_task.id
                })
                
            except Exception as e:
                logger.error(f"Failed to process project {project_id}: {e}")
                results["failed"].append({
                    "project_id": project_id,
                    "error": str(e)
                })
        
        self.update_progress(task_id, 100, "completed")
        
        return {
            "batch_id": task_id,
            "total": total,
            "successful": len(results["successful"]),
            "failed": len(results["failed"]),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Batch content generation failed: {e}")
        raise

# ============================================================================
# CONTENT OPTIMIZATION TASKS
# ============================================================================

@shared_task(
    bind=True,
    name="optimize_for_platform",
    queue="content",
    max_retries=2
)
def optimize_content_for_platform_task(
    self: Task,
    project_id: int,
    platform: str
) -> Dict[str, Any]:
    """
    Optimize content for specific platform
    
    Priority: Normal
    Queue: content
    Timeout: 3 minutes
    """
    
    task_id = self.request.id
    
    try:
        self.update_progress(task_id, 0, "loading_project")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Get project
            project_data = loop.run_until_complete(
                get_project_data(project_id)
            )
            
            if not project_data["script"]:
                raise ValueError("Project has no script to optimize")
            
            self.update_progress(task_id, 30, "optimizing_content")
            
            # Optimize script
            optimized_script = loop.run_until_complete(
                content_service.integrate_trends(
                    project_data["script"],
                    platform
                )
            )
            
            # Generate platform-specific hashtags
            hashtags = loop.run_until_complete(
                content_service.generate_hashtags(
                    project_data["topic"],
                    project_data["target_audience"]
                )
            )
            
            self.update_progress(task_id, 70, "saving_updates")
            
            # Update project
            loop.run_until_complete(
                update_project_content(
                    project_id,
                    optimized_script,
                    hashtags
                )
            )
            
            self.update_progress(task_id, 100, "completed")
            
            return {
                "success": True,
                "project_id": project_id,
                "platform": platform,
                "changes": [
                    "Updated script with platform trends",
                    "Generated platform-specific hashtags",
                    "Optimized pacing and CTAs"
                ]
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Platform optimization failed: {e}")
        raise self.retry(exc=e)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def save_content_to_project(
    project_id: int,
    script: str,
    hashtags: List[str],
    title: str,
    content_score: float
):
    """Save generated content to project"""
    
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Project)
            .where(Project.id == project_id)
            .values(
                script=script,
                hashtags=hashtags,
                title=title,
                updated_at=datetime.utcnow()
            )
        )
        await db.commit()
        
        logger.info(f"Content saved to project {project_id}")

async def get_project_data(project_id: int) -> Dict[str, Any]:
    """Get project data from database"""
    
    from sqlalchemy import select
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        return {
            "script": project.script,
            "topic": project.topic,
            "target_audience": project.target_audience
        }

async def update_project_content(
    project_id: int,
    script: str,
    hashtags: List[str]
):
    """Update project content"""
    
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Project)
            .where(Project.id == project_id)
            .values(
                script=script,
                hashtags=hashtags,
                updated_at=datetime.utcnow()
            )
        )
        await db.commit()

# ============================================================================
# SCHEDULED TASKS
# ============================================================================

@shared_task(name="refresh_trending_topics")
def refresh_trending_topics_task():
    """
    Refresh trending topics cache (scheduled task)
    Runs every 6 hours
    """
    
    try:
        # This would connect to trend APIs in production
        logger.info("Refreshing trending topics...")
        
        # Update Redis cache with trending topics
        import redis
        from ..config import settings
        
        redis_client = redis.from_url(settings.REDIS_URL)
        
        trending_topics = {
            "general": [
                "AI and Technology",
                "Sustainable Living",
                "Mental Health",
                "Quick Recipes",
                "Productivity Tips"
            ],
            "gaming": [
                "New Game Releases",
                "Speed Running",
                "Gaming Setups",
                "Retro Gaming",
                "E-Sports"
            ]
        }
        
        redis_client.setex(
            "content:trending_topics",
            21600,  # 6 hours
            json.dumps(trending_topics)
        )
        
        logger.info("Trending topics updated successfully")
        
    except Exception as e:
        logger.error(f"Failed to refresh trending topics: {e}")
