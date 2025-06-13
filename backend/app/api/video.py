# backend/app/api/video.py
"""
🎬 REELS GENERATOR - Video Processing API
Endpoints for video generation, composition, and effects
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from ..database import get_db
from ..models import User, Project, ProjectStatus
from ..schemas import ProjectResponse
from ..services.video_processing import video_service
from ..services.file_storage import storage_service
from .auth import get_current_active_user

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# ============================================================================
# VIDEO GENERATION ENDPOINTS
# ============================================================================

@router.post("/generate/{project_id}", response_model=ProjectResponse)
async def generate_video(
    project_id: int,
    background_video: str = "minecraft",
    subtitle_style: str = "default",
    subtitle_animation: str = "word_by_word",
    music_volume: float = Query(0.1, ge=0, le=1),
    transitions: bool = True,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ProjectResponse:
    """
    Generate video for a project
    
    Creates a complete video with:
    - TTS audio narration
    - Animated subtitles
    - Background video/gameplay
    - Background music (optional)
    - Transition effects
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
    
    # Validate project state
    if not project.script:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no script. Generate content first."
        )
    
    if not project.audio_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no audio. Generate TTS first."
        )
    
    if project.status == ProjectStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Video is already being processed"
        )
    
    # Update project status
    project.status = ProjectStatus.PROCESSING
    project.processing_started_at = datetime.utcnow()
    await db.commit()
    
    # Start video generation in background
    background_tasks.add_task(
        process_video_generation,
        project_id=project_id,
        audio_url=project.audio_file_path,
        script=project.script,
        background_video=background_video,
        subtitle_style=subtitle_style,
        subtitle_animation=subtitle_animation,
        music_volume=music_volume,
        transitions=transitions,
        user_id=current_user.id
    )
    
    await db.refresh(project)
    
    return project

@router.get("/backgrounds")
async def list_background_videos(
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, str]]:
    """
    Get available background videos
    
    Returns list of pre-loaded background videos for different styles.
    """
    
    backgrounds = [
        {
            "id": "minecraft",
            "name": "Minecraft Parkour",
            "description": "Popular Minecraft parkour gameplay",
            "category": "gaming",
            "preview_url": f"{storage_service.cdn_url}/previews/minecraft.jpg"
        },
        {
            "id": "subway_surfers",
            "name": "Subway Surfers",
            "description": "Endless runner mobile game footage",
            "category": "gaming",
            "preview_url": f"{storage_service.cdn_url}/previews/subway_surfers.jpg"
        },
        {
            "id": "gta",
            "name": "GTA Driving",
            "description": "GTA 5 driving gameplay",
            "category": "gaming",
            "preview_url": f"{storage_service.cdn_url}/previews/gta.jpg"
        },
        {
            "id": "nature",
            "name": "Nature Scenery",
            "description": "Calming nature footage",
            "category": "relaxing",
            "preview_url": f"{storage_service.cdn_url}/previews/nature.jpg"
        },
        {
            "id": "abstract",
            "name": "Abstract Shapes",
            "description": "Modern abstract animations",
            "category": "creative",
            "preview_url": f"{storage_service.cdn_url}/previews/abstract.jpg"
        },
        {
            "id": "tech",
            "name": "Tech Animation",
            "description": "Futuristic tech visuals",
            "category": "professional",
            "preview_url": f"{storage_service.cdn_url}/previews/tech.jpg"
        }
    ]
    
    return backgrounds

@router.get("/subtitle-styles")
async def list_subtitle_styles(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get available subtitle styles
    
    Returns subtitle styling presets with previews.
    """
    
    styles = {
        "default": {
            "name": "Default",
            "description": "Clean white text with black outline",
            "preview": "Standard YouTube style",
            "settings": video_service.subtitle_styles["default"]
        },
        "modern": {
            "name": "Modern",
            "description": "Bold yellow text with strong outline",
            "preview": "Eye-catching TikTok style",
            "settings": video_service.subtitle_styles["modern"]
        },
        "minimal": {
            "name": "Minimal",
            "description": "Simple white text with shadow",
            "preview": "Clean Instagram style",
            "settings": video_service.subtitle_styles["minimal"]
        },
        "neon": {
            "name": "Neon",
            "description": "Glowing effect with color animation",
            "preview": "Cyberpunk style",
            "settings": {
                "fontname": "Arial Black",
                "fontsize": 30,
                "fontcolor": "cyan",
                "bordercolor": "magenta",
                "borderstyle": 3,
                "blur": 2
            }
        },
        "comic": {
            "name": "Comic",
            "description": "Comic book style with speech bubbles",
            "preview": "Fun animated style",
            "settings": {
                "fontname": "Comic Sans MS",
                "fontsize": 26,
                "fontcolor": "black",
                "box": 1,
                "boxcolor": "white",
                "borderstyle": 1
            }
        }
    }
    
    return styles

@router.post("/preview")
async def generate_preview(
    project_id: int,
    duration: int = Query(10, ge=5, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """
    Generate a preview clip of the video
    
    Creates a short preview (5-30 seconds) for testing settings.
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
    
    if not project.audio_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generate audio first"
        )
    
    # Generate preview
    # In production, this would create a short clip
    preview_url = f"{storage_service.cdn_url}/previews/preview_{project_id}.mp4"
    
    return {
        "preview_url": preview_url,
        "duration": duration,
        "message": "Preview generated successfully"
    }

# ============================================================================
# VIDEO EDITING ENDPOINTS
# ============================================================================

@router.post("/add-watermark/{project_id}")
async def add_watermark(
    project_id: int,
    watermark_text: str,
    position: str = Query("bottom_right", regex="^(top_left|top_right|bottom_left|bottom_right)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Add watermark to video
    
    Adds text watermark at specified position.
    """
    
    # Get project
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    
    if not project or not project.video_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    # Add watermark (simplified for example)
    watermarked_url = f"{project.video_file_path}?watermark={watermark_text}"
    
    return {
        "video_url": watermarked_url,
        "watermark": watermark_text,
        "position": position
    }

@router.post("/optimize/{project_id}")
async def optimize_video(
    project_id: int,
    platform: str = Query(..., regex="^(youtube|instagram|tiktok)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Optimize video for specific platform
    
    Re-encodes video with platform-specific settings.
    """
    
    # Get project
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    
    if not project or not project.video_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found"
        )
    
    # Platform optimization specs
    optimization_result = await video_service.optimize_for_platform(
        project.video_file_path,
        platform
    )
    
    return optimization_result

# ============================================================================
# VIDEO ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/analytics/{project_id}")
async def get_video_analytics(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get video processing analytics
    
    Returns detailed metrics about video generation.
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
    
    analytics = {
        "project_id": project_id,
        "status": project.status.value,
        "processing_time": project.processing_duration,
        "video_details": None
    }
    
    if project.video_file_path:
        # Get video metadata
        analytics["video_details"] = {
            "url": project.video_file_path,
            "duration": project.duration,
            "resolution": "1080x1920",
            "format": "mp4",
            "fps": 30,
            "thumbnail": project.thumbnail_path
        }
    
    return analytics

# ============================================================================
# BATCH OPERATIONS
# ============================================================================

@router.post("/batch-generate")
async def batch_generate_videos(
    project_ids: List[int],
    settings: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Generate videos for multiple projects
    
    Batch process video generation with same settings.
    Maximum 5 projects per batch.
    """
    
    if len(project_ids) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 projects per batch"
        )
    
    # Validate all projects
    valid_projects = []
    
    for project_id in project_ids:
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == current_user.id
            )
        )
        project = result.scalar_one_or_none()
        
        if project and project.audio_file_path and project.status != ProjectStatus.PROCESSING:
            valid_projects.append(project)
            project.status = ProjectStatus.PROCESSING
            project.processing_started_at = datetime.utcnow()
    
    await db.commit()
    
    # Queue batch processing
    for project in valid_projects:
        background_tasks.add_task(
            process_video_generation,
            project_id=project.id,
            audio_url=project.audio_file_path,
            script=project.script,
            **settings,
            user_id=current_user.id
        )
    
    return {
        "queued": len(valid_projects),
        "skipped": len(project_ids) - len(valid_projects),
        "project_ids": [p.id for p in valid_projects],
        "message": f"Batch video generation started for {len(valid_projects)} projects"
    }

# ============================================================================
# TEMPLATE ENDPOINTS
# ============================================================================

@router.get("/templates")
async def get_video_templates(
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get video generation templates
    
    Pre-configured settings for different content types.
    """
    
    templates = [
        {
            "id": "viral_gaming",
            "name": "Viral Gaming",
            "description": "High-energy gaming content with fast subtitles",
            "settings": {
                "background_video": "minecraft",
                "subtitle_style": "modern",
                "subtitle_animation": "word_by_word",
                "music_volume": 0.15,
                "transitions": True
            }
        },
        {
            "id": "educational",
            "name": "Educational",
            "description": "Clear, easy-to-read educational content",
            "settings": {
                "background_video": "abstract",
                "subtitle_style": "default",
                "subtitle_animation": "line_by_line",
                "music_volume": 0.05,
                "transitions": True
            }
        },
        {
            "id": "storytelling",
            "name": "Storytelling",
            "description": "Dramatic storytelling with karaoke subtitles",
            "settings": {
                "background_video": "nature",
                "subtitle_style": "minimal",
                "subtitle_animation": "karaoke",
                "music_volume": 0.2,
                "transitions": True
            }
        },
        {
            "id": "business",
            "name": "Business",
            "description": "Professional content with clean presentation",
            "settings": {
                "background_video": "tech",
                "subtitle_style": "minimal",
                "subtitle_animation": "line_by_line",
                "music_volume": 0.0,
                "transitions": False
            }
        }
    ]
    
    return templates

@router.post("/apply-template/{project_id}")
async def apply_video_template(
    project_id: int,
    template_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ProjectResponse:
    """
    Apply template and generate video
    
    Uses pre-configured template settings for video generation.
    """
    
    # Get template settings
    templates = {
        "viral_gaming": {
            "background_video": "minecraft",
            "subtitle_style": "modern",
            "subtitle_animation": "word_by_word",
            "music_volume": 0.15,
            "transitions": True
        },
        "educational": {
            "background_video": "abstract",
            "subtitle_style": "default",
            "subtitle_animation": "line_by_line",
            "music_volume": 0.05,
            "transitions": True
        },
        "storytelling": {
            "background_video": "nature",
            "subtitle_style": "minimal",
            "subtitle_animation": "karaoke",
            "music_volume": 0.2,
            "transitions": True
        },
        "business": {
            "background_video": "tech",
            "subtitle_style": "minimal",
            "subtitle_animation": "line_by_line",
            "music_volume": 0.0,
            "transitions": False
        }
    }
    
    if template_id not in templates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    settings = templates[template_id]
    
    # Generate video with template settings
    return await generate_video(
        project_id=project_id,
        background_tasks=background_tasks,
        db=db,
        current_user=current_user,
        **settings
    )

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def process_video_generation(
    project_id: int,
    audio_url: str,
    script: str,
    background_video: str,
    subtitle_style: str,
    subtitle_animation: str,
    music_volume: float,
    transitions: bool,
    user_id: int
):
    """Background task for video generation"""
    
    from ..database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        try:
            logger.info(f"🎬 Starting video generation for project {project_id}")
            
            # Generate video
            result = await video_service.generate_video(
                audio_url=audio_url,
                script=script,
                background_video=background_video,
                subtitle_style=subtitle_style,
                subtitle_animation=subtitle_animation,
                music_volume=music_volume,
                transitions=transitions
            )
            
            # Update project
            await db.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(
                    video_file_path=result["video_url"],
                    thumbnail_path=result["thumbnail_url"],
                    status=ProjectStatus.COMPLETED,
                    processing_completed_at=datetime.utcnow(),
                    subtitle_style={
                        "style": subtitle_style,
                        "animation": subtitle_animation
                    }
                )
            )
            
            await db.commit()
            logger.info(f"✅ Video generation completed for project {project_id}")
            
        except Exception as e:
            logger.error(f"💥 Video generation failed for project {project_id}: {e}")
            
            # Update project status to failed
            await db.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(
                    status=ProjectStatus.FAILED,
                    error_message=str(e)
                )
            )
            
            await db.commit()
