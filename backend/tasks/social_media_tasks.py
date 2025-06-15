# backend/app/tasks/social_media_tasks.py
"""
📱 REELS GENERATOR - Social Media Tasks
Celery tasks for social media publishing and analytics
"""

from celery import shared_task, Task
from celery.exceptions import SoftTimeLimitExceeded
from typing import Dict, Any, List, Optional
import logging
import asyncio
from datetime import datetime, timedelta

from ..services.social_media import publishing_service
from ..database import AsyncSessionLocal
from ..models import Publication, SocialAccount, Platform
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

# ============================================================================
# PUBLISHING TASKS
# ============================================================================

@shared_task(
    bind=True,
    name="publish_to_platform",
    queue="social",
    max_retries=3,
    default_retry_delay=300  # 5 minutes
)
def publish_to_platform_task(
    self: Task,
    project_id: int,
    platform: str,
    social_account_id: int,
    settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Publish video to a specific platform
    
    Priority: High
    Queue: social
    Timeout: 10 minutes
    """
    
    task_id = self.request.id
    logger.info(f"Publishing project {project_id} to {platform}")
    
    try:
        self.update_progress(task_id, 0, "preparing")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Get project and social account
            async with AsyncSessionLocal() as db:
                self.update_progress(task_id, 20, "uploading_video")
                
                # Publish using service
                result = await publishing_service.publish_to_platforms(
                    project_id=project_id,
                    platforms=[platform],
                    **settings
                )
                
                self.update_progress(task_id, 80, "finalizing")
                
                if result["successful"]:
                    self.update_progress(task_id, 100, "completed")
                    
                    # Schedule analytics update
                    schedule_analytics_update.apply_async(
                        args=[project_id, platform],
                        countdown=300  # 5 minutes
                    )
                    
                    return {
                        "success": True,
                        "platform": platform,
                        "url": result["successful"][0]["url"],
                        "post_id": result["successful"][0]["post_id"]
                    }
                else:
                    error = result["failed"][0]["error"]
                    raise Exception(error)
                    
        finally:
            loop.close()
            
    except SoftTimeLimitExceeded:
        logger.error(f"Publishing task {task_id} timed out")
        self.update_progress(task_id, -1, "timeout")
        raise
        
    except Exception as e:
        logger.error(f"Publishing failed: {e}")
        self.update_progress(task_id, -1, "failed", {"error": str(e)})
        raise self.retry(exc=e)

@shared_task(
    bind=True,
    name="batch_publish",
    queue="social",
    max_retries=2
)
def batch_publish_task(
    self: Task,
    project_ids: List[int],
    platforms: List[str],
    settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Publish multiple videos to multiple platforms
    
    Priority: Normal
    Queue: social
    Timeout: 30 minutes
    """
    
    task_id = self.request.id
    results = {
        "successful": [],
        "failed": []
    }
    
    try:
        total_tasks = len(project_ids) * len(platforms)
        completed = 0
        
        for project_id in project_ids:
            for platform in platforms:
                try:
                    # Submit individual publish task
                    sub_task = publish_to_platform_task.apply_async(
                        args=[project_id, platform],
                        kwargs={"settings": settings}
                    )
                    
                    results["successful"].append({
                        "project_id": project_id,
                        "platform": platform,
                        "task_id": sub_task.id
                    })
                    
                except Exception as e:
                    results["failed"].append({
                        "project_id": project_id,
                        "platform": platform,
                        "error": str(e)
                    })
                
                completed += 1
                progress = (completed / total_tasks) * 100
                self.update_progress(task_id, progress, f"processing_{completed}/{total_tasks}")
        
        self.update_progress(task_id, 100, "completed")
        
        return {
            "batch_id": task_id,
            "total_tasks": total_tasks,
            "successful": len(results["successful"]),
            "failed": len(results["failed"]),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Batch publishing failed: {e}")
        raise

# ============================================================================
# SCHEDULED PUBLISHING
# ============================================================================

@shared_task(
    name="schedule_publication",
    queue="social"
)
def schedule_publication_task(
    project_id: int,
    platforms: List[str],
    scheduled_for: str,
    **kwargs
):
    """
    Handle scheduled publication
    
    This task is scheduled to run at the specified time
    """
    
    logger.info(f"Executing scheduled publication for project {project_id}")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            publishing_service.publish_to_platforms(
                project_id=project_id,
                platforms=platforms,
                **kwargs
            )
        )
        
        logger.info(f"Scheduled publication completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Scheduled publication failed: {e}")
        raise
    finally:
        loop.close()

# ============================================================================
# ANALYTICS TASKS
# ============================================================================

@shared_task(
    name="update_platform_analytics",
    queue="social",
    max_retries=3
)
def update_platform_analytics_task(
    publication_id: int
):
    """
    Update analytics for a specific publication
    
    Priority: Low
    Queue: social
    """
    
    logger.info(f"Updating analytics for publication {publication_id}")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(
            publishing_service.update_publication_analytics(publication_id)
        )
        
        logger.info(f"Analytics updated for publication {publication_id}")
        
    except Exception as e:
        logger.error(f"Analytics update failed: {e}")
        raise
    finally:
        loop.close()

@shared_task(
    name="schedule_analytics_update",
    queue="social"
)
def schedule_analytics_update(
    project_id: int,
    platform: str
):
    """
    Schedule periodic analytics updates
    """
    
    # Update immediately
    update_project_analytics.apply_async(
        args=[project_id, platform]
    )
    
    # Schedule updates at intervals
    intervals = [
        300,     # 5 minutes
        1800,    # 30 minutes
        3600,    # 1 hour
        7200,    # 2 hours
        21600,   # 6 hours
        43200,   # 12 hours
        86400,   # 24 hours
        172800,  # 48 hours
        604800   # 1 week
    ]
    
    for interval in intervals:
        update_project_analytics.apply_async(
            args=[project_id, platform],
            countdown=interval
        )

@shared_task(
    name="update_project_analytics",
    queue="social"
)
def update_project_analytics(
    project_id: int,
    platform: str
):
    """
    Update analytics for a project's publication on a platform
    """
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        async with AsyncSessionLocal() as db:
            # Find publication
            result = await db.execute(
                select(Publication).join(
                    SocialAccount
                ).where(
                    Publication.project_id == project_id,
                    SocialAccount.platform == Platform(platform)
                )
            )
            publication = result.scalar_one_or_none()
            
            if publication:
                loop.run_until_complete(
                    publishing_service.update_publication_analytics(publication.id)
                )
                
    except Exception as e:
        logger.error(f"Failed to update project analytics: {e}")
    finally:
        loop.close()

# ============================================================================
# ACCOUNT SYNC TASKS
# ============================================================================

@shared_task(
    name="sync_social_accounts",
    queue="social"
)
def sync_social_accounts_task(user_id: int):
    """
    Sync all social accounts for a user
    
    Updates follower counts and checks token validity
    """
    
    logger.info(f"Syncing social accounts for user {user_id}")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        async with AsyncSessionLocal() as db:
            # Get all active accounts
            result = await db.execute(
                select(SocialAccount).where(
                    SocialAccount.user_id == user_id,
                    SocialAccount.is_active == True
                )
            )
            accounts = result.scalars().all()
            
            for account in accounts:
                try:
                    # Refresh account data
                    from ..api.social_media import refresh_account_analytics
                    loop.run_until_complete(
                        refresh_account_analytics(account.id)
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to sync account {account.id}: {e}")
                    
    except Exception as e:
        logger.error(f"Account sync failed: {e}")
    finally:
        loop.close()

# ============================================================================
# WEBHOOK PROCESSING
# ============================================================================

@shared_task(
    name="process_platform_webhook",
    queue="social",
    max_retries=3
)
def process_platform_webhook_task(
    platform: str,
    webhook_data: Dict[str, Any]
):
    """
    Process incoming webhook from social media platform
    
    Handles analytics updates, status changes, etc.
    """
    
    logger.info(f"Processing {platform} webhook")
    
    try:
        if platform == "youtube":
            process_youtube_webhook(webhook_data)
        elif platform == "instagram":
            process_instagram_webhook(webhook_data)
        elif platform == "tiktok":
            process_tiktok_webhook(webhook_data)
        else:
            logger.warning(f"Unknown platform webhook: {platform}")
            
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise

def process_youtube_webhook(data: Dict[str, Any]):
    """Process YouTube webhook data"""
    
    # YouTube sends notifications for:
    # - New comments
    # - Video statistics updates
    # - Channel subscription changes
    
    if "video_id" in data:
        # Update video analytics
        update_platform_analytics_task.delay(
            video_id=data["video_id"],
            platform="youtube"
        )

def process_instagram_webhook(data: Dict[str, Any]):
    """Process Instagram webhook data"""
    
    # Instagram webhooks for:
    # - Media insights updates
    # - Comments and mentions
    # - Account insights
    
    for entry in data.get("entry", []):
        if "changes" in entry:
            for change in entry["changes"]:
                if change["field"] == "insights":
                    # Update insights
                    media_id = change["value"].get("media_id")
                    if media_id:
                        update_platform_analytics_task.delay(
                            media_id=media_id,
                            platform="instagram"
                        )

def process_tiktok_webhook(data: Dict[str, Any]):
    """Process TikTok webhook data"""
    
    # TikTok webhooks for:
    # - Video performance updates
    # - Comment notifications
    
    event_type = data.get("event_type")
    
    if event_type == "video.stats.updated":
        video_id = data.get("object_id")
        if video_id:
            update_platform_analytics_task.delay(
                video_id=video_id,
                platform="tiktok"
            )

# ============================================================================
# SCHEDULED TASKS
# ============================================================================

@shared_task(name="daily_analytics_summary")
def daily_analytics_summary_task():
    """
    Generate daily analytics summary for all users
    
    Runs daily at midnight
    """
    
    logger.info("Generating daily analytics summaries")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        async with AsyncSessionLocal() as db:
            # Get all users with published content
            result = await db.execute(
                select(User).join(
                    Project
                ).join(
                    Publication
                ).where(
                    Publication.is_published == True
                ).distinct()
            )
            users = result.scalars().all()
            
            for user in users:
                try:
                    # Generate summary
                    generate_user_analytics_summary.delay(user.id)
                    
                except Exception as e:
                    logger.error(f"Failed to generate summary for user {user.id}: {e}")
                    
    except Exception as e:
        logger.error(f"Daily analytics summary failed: {e}")
    finally:
        loop.close()

@shared_task(name="check_scheduled_publications")
def check_scheduled_publications_task():
    """
    Check for publications that should be published now
    
    Runs every 5 minutes
    """
    
    logger.info("Checking scheduled publications")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        async with AsyncSessionLocal() as db:
            # Find publications scheduled for now
            now = datetime.utcnow()
            cutoff = now + timedelta(minutes=5)
            
            result = await db.execute(
                select(Publication).where(
                    Publication.is_published == False,
                    Publication.scheduled_for != None,
                    Publication.scheduled_for <= cutoff
                )
            )
            publications = result.scalars().all()
            
            for pub in publications:
                # Submit publication task
                publish_scheduled_content.delay(pub.id)
                
    except Exception as e:
        logger.error(f"Scheduled publication check failed: {e}")
    finally:
        loop.close()
