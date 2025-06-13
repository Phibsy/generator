# backend/app/api/content.py
"""
📝 REELS GENERATOR - Content Generation API
Endpoints for AI-powered content creation and management
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Dict, Any
import logging

from ..database import get_db
from ..models import User, Project, ProjectStatus
from ..schemas import (
    ContentGenerationRequest, 
    ContentGenerationResponse,
    ProjectResponse,
    ErrorResponse
)
from ..services.content_generation import content_service
from .auth import get_current_active_user

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# ============================================================================
# CONTENT GENERATION ENDPOINTS
# ============================================================================

@router.post("/generate", response_model=ContentGenerationResponse)
async def generate_content(
    request: ContentGenerationRequest,
    current_user: User = Depends(get_current_active_user)
) -> ContentGenerationResponse:
    """
    Generate AI-powered video script and hashtags
    
    This endpoint uses GPT-4 to create engaging short-form video content
    optimized for maximum engagement on social platforms.
    """
    
    # Check user limits
    if not current_user.can_generate_video:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Monthly limit reached. You've generated {current_user.videos_generated}/{current_user.monthly_limit} videos this month."
        )
    
    try:
        # Generate content
        logger.info(f"🎬 Generating content for user {current_user.username} - Topic: {request.topic}")
        content = await content_service.generate_story(request)
        
        logger.info(f"✅ Content generated successfully - Score: {content.content_score}")
        return content
        
    except Exception as e:
        logger.error(f"💥 Content generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Content generation failed. Please try again."
        )

@router.post("/generate-hashtags", response_model=List[str])
async def generate_hashtags(
    topic: str,
    target_audience: str,
    platform: str = "instagram",
    current_user: User = Depends(get_current_active_user)
) -> List[str]:
    """
    Generate optimized hashtags for a specific topic
    
    Returns a mix of high-volume, medium-volume, and niche hashtags
    for maximum reach and engagement.
    """
    
    try:
        hashtags = await content_service.generate_hashtags(topic, target_audience)
        
        # Platform-specific additions
        if platform == "instagram":
            hashtags = ["reels", "reelsinstagram", "reelsvideo"] + hashtags
        elif platform == "youtube":
            hashtags = ["shorts", "youtubeshorts", "ytshorts"] + hashtags
        elif platform == "tiktok":
            hashtags = ["fyp", "foryou", "foryoupage"] + hashtags
        
        return hashtags[:30]  # Instagram limit
        
    except Exception as e:
        logger.error(f"💥 Hashtag generation failed: {e}")
        return ["viral", "trending", "fyp", "shorts", "reels"]  # Fallback

@router.post("/analyze-content", response_model=Dict[str, Any])
async def analyze_content(
    script: str,
    topic: str,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Analyze content quality and get improvement suggestions
    
    Uses AI to evaluate engagement potential and provide
    actionable feedback for content optimization.
    """
    
    try:
        analysis = await content_service.analyze_content_quality(script, topic)
        return analysis
        
    except Exception as e:
        logger.error(f"💥 Content analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Content analysis failed"
        )

@router.post("/generate-variations", response_model=List[str])
async def generate_variations(
    script: str,
    num_variations: int = 3,
    current_user: User = Depends(get_current_active_user)
) -> List[str]:
    """
    Generate script variations for A/B testing
    
    Creates multiple versions of a script with different hooks
    and CTAs to test which performs best.
    """
    
    if num_variations > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 variations allowed"
        )
    
    try:
        variations = await content_service.generate_variations(script, num_variations)
        return variations
        
    except Exception as e:
        logger.error(f"💥 Variation generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate variations"
        )

@router.post("/apply-to-project/{project_id}", response_model=ProjectResponse)
async def apply_content_to_project(
    project_id: int,
    content: ContentGenerationResponse,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ProjectResponse:
    """
    Apply generated content to an existing project
    
    Updates a project with the generated script and hashtags,
    preparing it for video processing.
    """
    
    # Get project
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if project.status != ProjectStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only apply content to draft projects"
        )
    
    # Update project with content
    project.script = content.script
    project.hashtags = content.hashtags
    project.title = content.suggested_title
    project.duration = content.estimated_duration
    
    # Update user video count
    current_user.videos_generated += 1
    
    await db.commit()
    await db.refresh(project)
    
    logger.info(f"✅ Content applied to project {project_id}")
    return project

@router.post("/optimize-for-platform/{platform}")
async def optimize_for_platform(
    script: str,
    platform: str,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Optimize content for a specific platform
    
    Adjusts script, timing, and format for platform-specific
    best practices and algorithm preferences.
    """
    
    valid_platforms = ["youtube", "instagram", "tiktok"]
    if platform not in valid_platforms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Platform must be one of: {valid_platforms}"
        )
    
    try:
        # Platform-specific optimizations
        optimized_script = await content_service.integrate_trends(script, platform)
        
        # Platform-specific recommendations
        recommendations = {
            "youtube": {
                "ideal_duration": 60,
                "aspect_ratio": "9:16",
                "max_hashtags": 15,
                "description_length": 100,
                "best_posting_times": ["12:00", "17:00", "20:00"]
            },
            "instagram": {
                "ideal_duration": 30,
                "aspect_ratio": "9:16", 
                "max_hashtags": 30,
                "description_length": 2200,
                "best_posting_times": ["11:00", "14:00", "19:00"]
            },
            "tiktok": {
                "ideal_duration": 45,
                "aspect_ratio": "9:16",
                "max_hashtags": 10,
                "description_length": 150,
                "best_posting_times": ["06:00", "10:00", "21:00"]
            }
        }
        
        return {
            "optimized_script": optimized_script,
            "platform_settings": recommendations[platform],
            "changes_made": [
                "Added platform-specific trends",
                "Adjusted pacing for platform",
                "Optimized CTA for platform audience"
            ]
        }
        
    except Exception as e:
        logger.error(f"💥 Platform optimization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Platform optimization failed"
        )

@router.get("/templates/{style}")
async def get_content_templates(
    style: str,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get content templates for different video styles
    
    Returns pre-defined templates that can be customized
    for quick content creation.
    """
    
    templates = {
        "educational": {
            "name": "Educational Content",
            "description": "Teach your audience something new",
            "structure": {
                "hook": "Start with a surprising fact or question",
                "body": "Explain 3-5 key points clearly",
                "cta": "Ask viewers to comment their thoughts"
            },
            "example_topics": [
                "5 Psychology Facts That Will Blow Your Mind",
                "How to Learn Any Skill in 30 Days",
                "The Science Behind Procrastination"
            ]
        },
        "entertainment": {
            "name": "Entertainment Content",
            "description": "Entertain and engage your audience",
            "structure": {
                "hook": "Start with relatable scenario or POV",
                "body": "Build tension and deliver punchline",
                "cta": "Ask to share with friends"
            },
            "example_topics": [
                "POV: Your Mom Finds Your Report Card",
                "Types of People at the Gym",
                "Expectation vs Reality: Cooking Edition"
            ]
        },
        "gaming": {
            "name": "Gaming Content",
            "description": "Share gaming tips, tricks, and moments",
            "structure": {
                "hook": "Promise valuable tip or show epic moment",
                "body": "Demonstrate technique or share story",
                "cta": "Ask for their best gaming moments"
            },
            "example_topics": [
                "Secret Trick Pro Players Don't Want You to Know",
                "1 vs 100 Clutch Victory",
                "Settings That Will Improve Your Aim Instantly"
            ]
        },
        "business": {
            "name": "Business Content",
            "description": "Share business insights and tips",
            "structure": {
                "hook": "Start with income claim or success story",
                "body": "Share actionable business advice",
                "cta": "Offer free resource or follow for more"
            },
            "example_topics": [
                "How I Made $10k in 30 Days",
                "3 Business Ideas You Can Start Today",
                "The Email That Gets 90% Response Rate"
            ]
        }
    }
    
    if style not in templates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found. Available styles: {list(templates.keys())}"
        )
    
    return templates[style]

@router.get("/trending-topics")
async def get_trending_topics(
    category: str = "general",
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get trending topics for content inspiration
    
    Returns current trending topics in different categories
    to help users create relevant content.
    """
    
    # In production, this would connect to trend APIs
    trending_topics = {
        "general": [
            {"topic": "AI and ChatGPT Tips", "engagement_score": 0.95},
            {"topic": "Sustainable Living Hacks", "engagement_score": 0.87},
            {"topic": "Mental Health Awareness", "engagement_score": 0.92},
            {"topic": "Quick Recipes Under 5 Minutes", "engagement_score": 0.88},
            {"topic": "Productivity Systems", "engagement_score": 0.85}
        ],
        "gaming": [
            {"topic": "New Game Release Reviews", "engagement_score": 0.94},
            {"topic": "Speed Running Techniques", "engagement_score": 0.86},
            {"topic": "Gaming Setup Tours", "engagement_score": 0.91},
            {"topic": "Retro Gaming Nostalgia", "engagement_score": 0.83},
            {"topic": "E-Sports Highlights", "engagement_score": 0.89}
        ],
        "education": [
            {"topic": "Study Techniques That Work", "engagement_score": 0.90},
            {"topic": "Language Learning Tips", "engagement_score": 0.88},
            {"topic": "Science Experiments at Home", "engagement_score": 0.85},
            {"topic": "History's Untold Stories", "engagement_score": 0.82},
            {"topic": "Math Tricks and Shortcuts", "engagement_score": 0.79}
        ]
    }
    
    topics = trending_topics.get(category, trending_topics["general"])
    
    # Sort by engagement score
    topics.sort(key=lambda x: x["engagement_score"], reverse=True)
    
    return topics

# ============================================================================
# BATCH OPERATIONS
# ============================================================================

@router.post("/batch-generate")
async def batch_generate_content(
    requests: List[ContentGenerationRequest],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Generate multiple content pieces in batch
    
    Queues multiple content generation tasks for processing.
    Maximum 10 per batch.
    """
    
    if len(requests) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 requests per batch"
        )
    
    # Check user limits
    if current_user.videos_generated + len(requests) > current_user.monthly_limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Batch would exceed monthly limit. Remaining: {current_user.monthly_limit - current_user.videos_generated}"
        )
    
    # Queue tasks
    batch_id = f"batch_{current_user.id}_{datetime.now().timestamp()}"
    
    for i, request in enumerate(requests):
        background_tasks.add_task(
            process_content_generation,
            request,
            current_user.id,
            batch_id,
            i
        )
    
    return {
        "batch_id": batch_id,
        "total_requests": len(requests),
        "status": "processing",
        "message": "Content generation started. Check status endpoint for updates."
    }

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def process_content_generation(
    request: ContentGenerationRequest,
    user_id: int,
    batch_id: str,
    index: int
):
    """Background task for content generation"""
    try:
        logger.info(f"Processing batch {batch_id} - Item {index}")
        # This would be handled by Celery in production
        content = await content_service.generate_story(request)
        # Store results in cache/database
        logger.info(f"Completed batch {batch_id} - Item {index}")
    except Exception as e:
        logger.error(f"Failed batch {batch_id} - Item {index}: {e}")
