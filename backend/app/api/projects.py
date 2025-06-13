# backend/app/api/projects.py
"""
📁 REELS GENERATOR - Project Management API
Enhanced project endpoints with content generation integration
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from typing import List, Optional
import logging
from datetime import datetime

from ..database import get_db
from ..models import User, Project, ProjectStatus, VideoAnalytics
from ..schemas import (
    ProjectCreate, 
    ProjectUpdate, 
    ProjectResponse,
    ContentGenerationRequest,
    ContentGenerationResponse,
    PaginationParams,
    PaginatedResponse
)
from ..services.content_generation import content_service
from .auth import get_current_active_user

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# ============================================================================
# PROJECT CRUD OPERATIONS
# ============================================================================

@router.post("/", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ProjectResponse:
    """
    Create a new project with optional auto-content generation
    """
    
    # Check user limits
    if not current_user.can_generate_video:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Monthly limit reached. You've created {current_user.videos_generated}/{current_user.monthly_limit} videos this month."
        )
    
    # Create project
    db_project = Project(
        user_id=current_user.id,
        title=project_data.title,
        description=project_data.description,
        topic=project_data.topic,
        target_audience=project_data.target_audience,
        video_style=project_data.video_style,
        duration=project_data.duration,
        voice_id=project_data.voice_id,
        background_music=project_data.background_music,
        subtitle_style=project_data.subtitle_style
    )
    
    db.add(db_project)
    await db.commit()
    await db.refresh(db_project)
    
    # Auto-generate content if topic is provided
    if project_data.topic and project_data.target_audience:
        background_tasks.add_task(
            auto_generate_content,
            db_project.id,
            project_data.topic,
            project_data.target_audience,
            project_data.video_style or "educational",
            project_data.duration
        )
        logger.info(f"🎬 Auto-generating content for project {db_project.id}")
    
    return db_project

@router.get("/", response_model=PaginatedResponse)
async def list_projects(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[ProjectStatus] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all projects for the current user with filtering and pagination
    """
    
    # Base query
    query = select(Project).where(Project.user_id == current_user.id)
    
    # Apply filters
    if status_filter:
        query = query.where(Project.status == status_filter)
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Project.title.ilike(search_term)) |
            (Project.description.ilike(search_term)) |
            (Project.topic.ilike(search_term))
        )
    
    # Order by creation date
    query = query.order_by(Project.created_at.desc())
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Apply pagination
    query = query.offset((pagination.page - 1) * pagination.limit).limit(pagination.limit)
    
    # Execute query
    result = await db.execute(query)
    projects = result.scalars().all()
    
    # Calculate pagination info
    pages = (total + pagination.limit - 1) // pagination.limit
    
    return PaginatedResponse(
        items=projects,
        total=total,
        page=pagination.page,
        limit=pagination.limit,
        pages=pages,
        has_next=pagination.page < pages,
        has_prev=pagination.page > 1
    )

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ProjectResponse:
    """
    Get a specific project by ID
    """
    
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
    
    return project

@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_update: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ProjectResponse:
    """
    Update a project (only allowed for draft projects)
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
            detail="Can only update draft projects"
        )
    
    # Update fields
    update_data = project_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    project.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(project)
    
    return project

@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a project and all associated data
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
    
    # Delete project (cascade will handle related records)
    await db.delete(project)
    await db.commit()
    
    return {"message": "Project deleted successfully"}

# ============================================================================
# CONTENT GENERATION ENDPOINTS
# ============================================================================

@router.post("/{project_id}/generate-content", response_model=ProjectResponse)
async def generate_project_content(
    project_id: int,
    regenerate: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ProjectResponse:
    """
    Generate or regenerate content for a project
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
    
    # Check if content already exists
    if project.script and not regenerate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content already exists. Set regenerate=true to create new content."
        )
    
    # Check project has required fields
    if not project.topic or not project.target_audience:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project must have topic and target_audience to generate content"
        )
    
    try:
        # Create content generation request
        content_request = ContentGenerationRequest(
            topic=project.topic,
            target_audience=project.target_audience,
            video_style=project.video_style or "educational",
            duration=project.duration,
            tone="engaging",
            include_call_to_action=True
        )
        
        # Generate content
        content = await content_service.generate_story(content_request)
        
        # Update project
        project.script = content.script
        project.hashtags = content.hashtags
        project.title = content.suggested_title if not project.title else project.title
        
        # Update user count if regenerating
        if regenerate:
            current_user.videos_generated += 1
        
        # Create analytics entry
        analytics = VideoAnalytics(
            project_id=project.id,
            content_score=content.content_score,
            script_length=len(content.script),
            hashtag_count=len(content.hashtags)
        )
        db.add(analytics)
        
        await db.commit()
        await db.refresh(project)
        
        logger.info(f"✅ Content generated for project {project_id}")
        return project
        
    except Exception as e:
        logger.error(f"💥 Content generation failed for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Content generation failed"
        )

@router.post("/{project_id}/optimize-content")
async def optimize_project_content(
    project_id: int,
    platform: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Optimize project content for a specific platform
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
    
    if not project.script:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no content to optimize"
        )
    
    valid_platforms = ["youtube", "instagram", "tiktok"]
    if platform not in valid_platforms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Platform must be one of: {valid_platforms}"
        )
    
    try:
        # Optimize content
        optimized_script = await content_service.integrate_trends(project.script, platform)
        
        # Generate platform-specific hashtags
        hashtags = await content_service.generate_hashtags(project.topic, project.target_audience)
        
        # Update project
        project.script = optimized_script
        project.hashtags = hashtags[:30]  # Platform limit
        
        await db.commit()
        
        return {
            "message": f"Content optimized for {platform}",
            "changes_made": [
                "Updated script with platform trends",
                "Generated platform-specific hashtags",
                "Adjusted pacing and CTAs"
            ]
        }
        
    except Exception as e:
        logger.error(f"💥 Content optimization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Content optimization failed"
        )

@router.get("/{project_id}/content-analysis")
async def analyze_project_content(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get detailed content analysis for a project
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
    
    if not project.script:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no content to analyze"
        )
    
    try:
        # Analyze content
        analysis = await content_service.analyze_content_quality(
            project.script,
            project.topic
        )
        
        # Add project-specific metrics
        analysis["project_metrics"] = {
            "script_length": len(project.script),
            "word_count": len(project.script.split()),
            "hashtag_count": len(project.hashtags) if project.hashtags else 0,
            "estimated_duration": len(project.script.split()) / 2.5,
            "readability_score": calculate_readability(project.script)
        }
        
        return analysis
        
    except Exception as e:
        logger.error(f"💥 Content analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Content analysis failed"
        )

# ============================================================================
# PROJECT STATUS MANAGEMENT
# ============================================================================

@router.post("/{project_id}/status/{new_status}")
async def update_project_status(
    project_id: int,
    new_status: ProjectStatus,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update project status (for admin/testing purposes)
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
    
    # Update status
    old_status = project.status
    project.status = new_status
    
    # Update timestamps based on status
    if new_status == ProjectStatus.PROCESSING:
        project.processing_started_at = datetime.utcnow()
    elif new_status == ProjectStatus.COMPLETED:
        project.processing_completed_at = datetime.utcnow()
    
    await db.commit()
    
    return {
        "message": f"Status updated from {old_status} to {new_status}",
        "project_id": project_id,
        "new_status": new_status
    }

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def auto_generate_content(
    project_id: int,
    topic: str,
    target_audience: str,
    video_style: str,
    duration: int
):
    """Background task to auto-generate content for a project"""
    
    from ..database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        try:
            # Create content request
            content_request = ContentGenerationRequest(
                topic=topic,
                target_audience=target_audience,
                video_style=video_style,
                duration=duration,
                tone="engaging",
                include_call_to_action=True
            )
            
            # Generate content
            content = await content_service.generate_story(content_request)
            
            # Update project
            await db.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(
                    script=content.script,
                    hashtags=content.hashtags,
                    title=content.suggested_title
                )
            )
            
            # Create analytics
            analytics = VideoAnalytics(
                project_id=project_id,
                content_score=content.content_score,
                script_length=len(content.script),
                hashtag_count=len(content.hashtags)
            )
            db.add(analytics)
            
            await db.commit()
            logger.info(f"✅ Auto-generated content for project {project_id}")
            
        except Exception as e:
            logger.error(f"💥 Auto-generation failed for project {project_id}: {e}")

def calculate_readability(text: str) -> float:
    """Calculate simple readability score (0-1)"""
    
    sentences = text.split('.')
    words = text.split()
    
    if not sentences or not words:
        return 0.5
    
    avg_sentence_length = len(words) / len(sentences)
    
    # Simple scoring based on sentence length
    if avg_sentence_length < 10:
        return 0.9  # Very easy
    elif avg_sentence_length < 15:
        return 0.7  # Easy
    elif avg_sentence_length < 20:
        return 0.5  # Medium
    else:
        return 0.3  # Difficult
