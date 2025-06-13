# backend/app/api/advanced_video.py
"""
🎬 REELS GENERATOR - Advanced Video Processing API
Week 5: Enhanced video endpoints with real-time progress
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import uuid

from ..database import get_db
from ..models import User, Project, ProjectStatus
from ..schemas import ProjectResponse
from ..services.advanced_video_processing import advanced_video_service
from ..services.websocket_manager import ProgressBroadcaster
from .auth import get_current_active_user

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# ============================================================================
# ADVANCED VIDEO GENERATION
# ============================================================================

@router.post("/generate-advanced/{project_id}")
async def generate_advanced_video(
    project_id: int,
    background_video: str = "abstract",
    subtitle_style: str = "modern",
    subtitle_animation: str = Query("wave", regex="^(wave|typewriter|bounce|fade)$"),
    music_preset: Optional[str] = Query(None, regex="^(upbeat|chill|dramatic|gaming)$"),
    music_volume: float = Query(0.1, ge=0, le=1),
    effects_enabled: bool = True,
    effects_preset: str = Query("dynamic", regex="^(dynamic|smooth|minimal)$"),
    quality: str = Query("medium", regex="^(low|medium|high|ultra)$"),
    platform: Optional[str] = Query(None, regex="^(youtube|instagram|tiktok)$"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Generate video with advanced features:
    - Precise word-level subtitle timing
    - Background music with auto-ducking
    - Beat-synchronized visual effects
    - Real-time progress updates via WebSocket
    - Quality optimization presets
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
    if not project.script or not project.audio_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project must have script and audio before video generation"
        )
    
    if project.status == ProjectStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Video is already being processed"
        )
    
    # Create task ID
    task_id = f"advanced_video_{project_id}_{uuid.uuid4()}"
    
    # Update project status
    project.status = ProjectStatus.PROCESSING
    project.processing_started_at = datetime.utcnow()
    await db.commit()
    
    # Prepare settings
    processing_settings = {
        "background": background_video,
        "subtitle_style": subtitle_style,
        "subtitle_animation": subtitle_animation,
        "music_preset": music_preset,
        "music_volume": music_volume,
        "effects_enabled": effects_enabled,
        "effects_preset": effects_preset,
        "quality": quality,
        "platform": platform
    }
    
    # Start processing in background
    background_tasks.add_task(
        process_advanced_video_task,
        project_id=project_id,
        audio_url=project.audio_file_path,
        script=project.script,
        settings=processing_settings,
        task_id=task_id,
        user_id=current_user.id
    )
    
    return {
        "task_id": task_id,
        "status": "processing",
        "message": "Advanced video generation started. Track progress via WebSocket.",
        "websocket_url": f"/ws/{current_user.id}"
    }

# ============================================================================
# MUSIC LIBRARY ENDPOINTS
# ============================================================================

@router.get("/music-library")
async def get_music_library(
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """Get available background music presets"""
    
    return [
        {
            "id": "upbeat",
            "name": "Upbeat Energy",
            "description": "High-energy electronic music for exciting content",
            "bpm": 128,
            "mood": "energetic",
            "genres": ["electronic", "pop"],
            "preview_url": "/api/v1/video/music-preview/upbeat"
        },
        {
            "id": "chill",
            "name": "Chill Vibes",
            "description": "Relaxed lofi beats for calm content",
            "bpm": 90,
            "mood": "relaxed",
            "genres": ["lofi", "ambient"],
            "preview_url": "/api/v1/video/music-preview/chill"
        },
        {
            "id": "dramatic",
            "name": "Dramatic Epic",
            "description": "Cinematic orchestral music for impactful moments",
            "bpm": 100,
            "mood": "intense",
            "genres": ["orchestral", "cinematic"],
            "preview_url": "/api/v1/video/music-preview/dramatic"
        },
        {
            "id": "gaming",
            "name": "Gaming Hype",
            "description": "Intense electronic music for gaming content",
            "bpm": 140,
            "mood": "exciting",
            "genres": ["electronic", "dubstep"],
            "preview_url": "/api/v1/video/music-preview/gaming"
        }
    ]

@router.get("/music-preview/{music_id}")
async def preview_music(
    music_id: str,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """Get preview URL for background music"""
    
    # In production, return actual music preview URLs
    return {
        "music_id": music_id,
        "preview_url": f"https://cdn.example.com/music/previews/{music_id}.mp3",
        "duration": 30  # 30 second preview
    }

# ============================================================================
# EFFECTS PRESETS
# ============================================================================

@router.get("/effects-presets")
async def get_effects_presets(
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """Get available visual effects presets"""
    
    return [
        {
            "id": "dynamic",
            "name": "Dynamic",
            "description": "Beat-synchronized zooms and shakes",
            "effects": ["zoom_pulse", "shake", "color_shift"],
            "intensity": "high",
            "best_for": ["gaming", "action", "music"]
        },
        {
            "id": "smooth",
            "name": "Smooth",
            "description": "Gentle zooms and pans",
            "effects": ["slow_zoom", "pan", "fade"],
            "intensity": "low",
            "best_for": ["educational", "calm", "professional"]
        },
        {
            "id": "minimal",
            "name": "Minimal",
            "description": "Subtle effects only",
            "effects": ["fade"],
            "intensity": "very_low",
            "best_for": ["text_heavy", "serious", "corporate"]
        }
    ]

# ============================================================================
# SUBTITLE ANIMATIONS
# ============================================================================

@router.get("/subtitle-animations")
async def get_subtitle_animations(
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """Get available subtitle animation styles"""
    
    return [
        {
            "id": "wave",
            "name": "Wave",
            "description": "Words appear in a wave motion",
            "preview_gif": "/assets/animations/wave.gif",
            "best_for": ["energetic", "fun", "casual"]
        },
        {
            "id": "typewriter",
            "name": "Typewriter",
            "description": "Classic typewriter effect",
            "preview_gif": "/assets/animations/typewriter.gif",
            "best_for": ["professional", "educational", "tech"]
        },
        {
            "id": "bounce",
            "name": "Bounce",
            "description": "Words bounce in with spring effect",
            "preview_gif": "/assets/animations/bounce.gif",
            "best_for": ["playful", "kids", "entertainment"]
        },
        {
            "id": "fade",
            "name": "Fade",
            "description": "Simple fade in/out",
            "preview_gif": "/assets/animations/fade.gif",
            "best_for": ["minimal", "elegant", "serious"]
        }
    ]

# ============================================================================
# QUALITY SETTINGS
# ============================================================================

@router.get("/quality-presets")
async def get_quality_presets(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get video quality presets with details"""
    
    return {
        "low": {
            "name": "Low Quality",
            "description": "Fast processing, smaller file size",
            "resolution": "720x1280",
            "fps": 24,
            "bitrate": "2M",
            "estimated_size_per_minute": "15MB",
            "processing_speed": "fast"
        },
        "medium": {
            "name": "Medium Quality",
            "description": "Balanced quality and file size",
            "resolution": "1080x1920",
            "fps": 30,
            "bitrate": "4M",
            "estimated_size_per_minute": "30MB",
            "processing_speed": "normal"
        },
        "high": {
            "name": "High Quality",
            "description": "High quality for important content",
            "resolution": "1080x1920",
            "fps": 60,
            "bitrate": "8M",
            "estimated_size_per_minute": "60MB",
            "processing_speed": "slow"
        },
        "ultra": {
            "name": "Ultra Quality",
            "description": "Maximum quality, large files",
            "resolution": "2160x3840",
            "fps": 60,
            "bitrate": "15M",
            "estimated_size_per_minute": "110MB",
            "processing_speed": "very_slow",
            "warning": "Not recommended for social media"
        }
    }

# ============================================================================
# BATCH PROCESSING
# ============================================================================

@router.post("/batch-generate-advanced")
async def batch_generate_advanced(
    project_ids: List[int],
    settings: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Generate multiple videos with advanced processing
    
    Processes up to 3 videos in parallel with shared settings
    """
    
    if len(project_ids) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 projects per batch"
        )
    
    # Validate all projects
    tasks = []
    
    for project_id in project_ids:
        result = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == current_user.id
            )
        )
        project = result.scalar_one_or_none()
        
        if project and project.audio_file_path and project.status != ProjectStatus.PROCESSING:
            task_id = f"batch_advanced_{project_id}_{uuid.uuid4()}"
            
            tasks.append({
                "project_id": project_id,
                "task_id": task_id,
                "audio_url": project.audio_file_path,
                "script": project.script
            })
            
            project.status = ProjectStatus.PROCESSING
            project.processing_started_at = datetime.utcnow()
    
    await db.commit()
    
    # Start batch processing
    background_tasks.add_task(
        process_batch_advanced,
        tasks=tasks,
        settings=settings,
        user_id=current_user.id
    )
    
    return {
        "batch_id": f"batch_{uuid.uuid4()}",
        "total_tasks": len(tasks),
        "task_ids": [t["task_id"] for t in tasks],
        "message": "Batch processing started"
    }

# ============================================================================
# PROGRESS TRACKING
# ============================================================================

@router.get("/task-status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get current status of a video processing task"""
    
    from ..services.websocket_manager import get_task_status as get_status
    
    status = await get_status(task_id)
    
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    return status

# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def process_advanced_video_task(
    project_id: int,
    audio_url: str,
    script: str,
    settings: Dict[str, Any],
    task_id: str,
    user_id: int
):
    """Background task for advanced video processing"""
    
    from ..database import AsyncSessionLocal
    
    # Create progress broadcaster
    progress = ProgressBroadcaster(task_id, str(user_id))
    
    async with AsyncSessionLocal() as db:
        try:
            # Process video with progress updates
            result = await advanced_video_service.process_advanced_video(
                project_id=project_id,
                audio_url=audio_url,
                script=script,
                settings=settings
            )
            
            # Update project
            await db.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(
                    video_file_path=result["video_url"],
                    status=ProjectStatus.COMPLETED,
                    processing_completed_at=datetime.utcnow()
                )
            )
            
            await db.commit()
            
            # Send completion
            await progress.complete({
                "video_url": result["video_url"],
                "processing_time": result["processing_time"]
            })
            
            logger.info(f"✅ Advanced video completed for project {project_id}")
            
        except Exception as e:
            logger.error(f"💥 Advanced video failed for project {project_id}: {e}")
            
            # Update project status
            await db.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(
                    status=ProjectStatus.FAILED,
                    error_message=str(e)
                )
            )
            
            await db.commit()
            
            # Send error
            await progress.error(str(e))

async def process_batch_advanced(
    tasks: List[Dict[str, Any]],
    settings: Dict[str, Any],
    user_id: int
):
    """Process multiple videos in parallel"""
    
    # Process with max 3 concurrent
    await advanced_video_service.process_batch_parallel(
        [
            {
                **task,
                "settings": settings,
                "user_id": user_id
            }
            for task in tasks
        ],
        max_concurrent=3
    )
