# backend/app/tasks/video_tasks.py
"""
🎬 REELS GENERATOR - Video Processing Tasks
Celery tasks for video generation and processing
"""

from celery import shared_task, Task, group, chain
from celery.exceptions import SoftTimeLimitExceeded
from typing import Dict, Any, List, Optional
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import os
import shutil
import uuid

from ..services.text_to_speech import tts_service
from ..services.video_processing import video_service
from ..services.advanced_video_processing import advanced_video_service
from ..services.file_storage import storage_service
from ..database import AsyncSessionLocal
from ..models import Project, ProjectStatus
from sqlalchemy import update, select

logger = logging.getLogger(__name__)

# ============================================================================
# TEXT-TO-SPEECH TASKS
# ============================================================================

@shared_task(
    bind=True,
    name="generate_tts",
    queue="content",
    max_retries=3,
    default_retry_delay=60
)
def generate_tts_task(
    self: Task,
    project_id: int,
    text: str,
    voice_id: str = "rachel",
    speed: float = 1.0
) -> Dict[str, Any]:
    """
    Generate text-to-speech audio
    
    Priority: High
    Queue: content
    Timeout: 5 minutes
    """
    
    task_id = self.request.id
    logger.info(f"Starting TTS generation task {task_id} for project {project_id}")
    
    try:
        self.update_progress(task_id, 0, "initializing")
        
        # Generate TTS
        self.update_progress(task_id, 30, "generating_audio")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                tts_service.generate_speech(
                    text=text,
                    voice_id=voice_id,
                    speed=speed
                )
            )
            
            self.update_progress(task_id, 80, "saving_audio")
            
            # Update project with audio path
            loop.run_until_complete(
                update_project_audio(project_id, result["audio_url"], voice_id)
            )
            
            self.update_progress(task_id, 100, "completed")
            
            logger.info(f"TTS generation completed for project {project_id}")
            
            return {
                "success": True,
                "project_id": project_id,
                "audio_url": result["audio_url"],
                "duration": result["duration"],
                "provider": result["provider"]
            }
            
        finally:
            loop.close()
            
    except SoftTimeLimitExceeded:
        logger.error(f"TTS task {task_id} timed out")
        self.update_progress(task_id, -1, "timeout")
        raise
        
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        self.update_progress(task_id, -1, "failed", {"error": str(e)})
        raise self.retry(exc=e)

# ============================================================================
# BASIC VIDEO PROCESSING TASKS
# ============================================================================

@shared_task(
    bind=True,
    name="generate_video",
    queue="video",
    max_retries=2,
    soft_time_limit=1800,  # 30 minutes
    time_limit=3600  # 1 hour
)
def generate_video_task(
    self: Task,
    project_id: int,
    audio_url: str,
    script: str,
    settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate basic video with subtitles
    
    Priority: Normal
    Queue: video
    Timeout: 30 minutes soft, 1 hour hard
    """
    
    task_id = self.request.id
    logger.info(f"Starting video generation task {task_id} for project {project_id}")
    
    try:
        # Update project status
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(
                update_project_status(project_id, ProjectStatus.PROCESSING)
            )
            
            self.update_progress(task_id, 10, "downloading_assets")
            
            # Generate video
            self.update_progress(task_id, 30, "processing_video")
            
            result = loop.run_until_complete(
                video_service.generate_video(
                    audio_url=audio_url,
                    script=script,
                    background_video=settings.get("background_video", "minecraft"),
                    subtitle_style=settings.get("subtitle_style", "default"),
                    subtitle_animation=settings.get("subtitle_animation", "word_by_word"),
                    music_volume=settings.get("music_volume", 0.1),
                    transitions=settings.get("transitions", True)
                )
            )
            
            self.update_progress(task_id, 80, "uploading_video")
            
            # Update project with video data
            loop.run_until_complete(
                update_project_video(
                    project_id,
                    result["video_url"],
                    result["thumbnail_url"],
                    result["metadata"]
                )
            )
            
            self.update_progress(task_id, 100, "completed")
            
            logger.info(f"Video generation completed for project {project_id}")
            
            return {
                "success": True,
                "project_id": project_id,
                "video_url": result["video_url"],
                "thumbnail_url": result["thumbnail_url"],
                "duration": result["duration"],
                "file_size": result["file_size"]
            }
            
        finally:
            loop.close()
            
    except SoftTimeLimitExceeded:
        logger.error(f"Video generation task {task_id} timed out")
        self.update_progress(task_id, -1, "timeout")
        raise
        
    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        self.update_progress(task_id, -1, "failed", {"error": str(e)})
        
        # Update project status to failed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            update_project_status(project_id, ProjectStatus.FAILED, str(e))
        )
        loop.close()
        
        raise self.retry(exc=e)

# ============================================================================
# ADVANCED VIDEO PROCESSING TASKS
# ============================================================================

@shared_task(
    bind=True,
    name="generate_advanced_video",
    queue="video",
    max_retries=2,
    soft_time_limit=2400,  # 40 minutes
    time_limit=3600  # 1 hour
)
def generate_advanced_video_task(
    self: Task,
    project_id: int,
    audio_url: str,
    script: str,
    settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate advanced video with effects and music
    
    Priority: High
    Queue: video (or gpu for ultra quality)
    Timeout: 40 minutes soft, 1 hour hard
    """
    
    task_id = self.request.id
    logger.info(f"Starting advanced video task {task_id} for project {project_id}")
    
    try:
        self.update_progress(task_id, 0, "initializing")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize progress tracking
            loop.run_until_complete(
                advanced_video_service.init_progress_tracking()
            )
            
            # Process video
            result = loop.run_until_complete(
                advanced_video_service.process_advanced_video(
                    project_id=project_id,
                    audio_url=audio_url,
                    script=script,
                    settings=settings
                )
            )
            
            logger.info(f"Advanced video completed for project {project_id}")
            
            return result
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Advanced video generation failed: {e}")
        raise self.retry(exc=e)

@shared_task(
    bind=True,
    name="process_ultra_quality_video",
    queue="gpu",
    max_retries=1,
    soft_time_limit=3600,  # 1 hour
    time_limit=7200  # 2 hours
)
def process_ultra_quality_video_task(
    self: Task,
    project_id: int,
    video_path: str,
    settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process video in ultra quality (4K)
    
    Priority: Highest
    Queue: gpu (dedicated GPU workers)
    Timeout: 1 hour soft, 2 hours hard
    """
    
    task_id = self.request.id
    
    try:
        self.update_progress(task_id, 0, "preparing_gpu_processing")
        
        # This task would be processed by GPU-enabled workers
        # with specialized hardware for 4K video processing
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Process with GPU acceleration
            result = loop.run_until_complete(
                advanced_video_service.optimize_quality(
                    Path(video_path),
                    quality_preset="ultra",
                    platform=settings.get("platform")
                )
            )
            
            self.update_progress(task_id, 100, "completed")
            
            return {
                "success": True,
                "project_id": project_id,
                "video_url": str(result),
                "quality": "ultra",
                "resolution": "2160x3840"
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Ultra quality processing failed: {e}")
        raise

# ============================================================================
# BATCH VIDEO PROCESSING
# ============================================================================

@shared_task(
    bind=True,
    name="batch_generate_videos",
    queue="video",
    max_retries=1
)
def batch_generate_videos_task(
    self: Task,
    project_ids: List[int],
    settings: Dict[str, Any],
    priority: int = 5
) -> Dict[str, Any]:
    """
    Generate videos for multiple projects
    
    Priority: Variable
    Queue: video
    Timeout: Depends on batch size
    """
    
    task_id = self.request.id
    
    try:
        self.update_progress(task_id, 0, "preparing_batch")
        
        # Create sub-tasks for each project
        tasks = []
        
        for project_id in project_ids:
            # Get project data
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                project_data = loop.run_until_complete(
                    get_project_for_video(project_id)
                )
                
                if project_data["audio_url"] and project_data["script"]:
                    # Create task signature
                    task = generate_video_task.signature(
                        args=[
                            project_id,
                            project_data["audio_url"],
                            project_data["script"]
                        ],
                        kwargs={"settings": settings},
                        priority=priority
                    )
                    tasks.append(task)
                    
            finally:
                loop.close()
        
        # Execute as group
        if tasks:
            self.update_progress(task_id, 20, "processing_batch")
            
            job = group(tasks)
            result = job.apply_async()
            
            # Wait for completion
            results = result.get()
            
            self.update_progress(task_id, 100, "completed")
            
            return {
                "batch_id": task_id,
                "total": len(project_ids),
                "processed": len(results),
                "results": results
            }
        else:
            return {
                "batch_id": task_id,
                "total": len(project_ids),
                "processed": 0,
                "error": "No valid projects for video generation"
            }
            
    except Exception as e:
        logger.error(f"Batch video generation failed: {e}")
        raise

# ============================================================================
# VIDEO OPTIMIZATION TASKS
# ============================================================================

@shared_task(
    bind=True,
    name="optimize_video_for_platform",
    queue="video",
    max_retries=2
)
def optimize_video_for_platform_task(
    self: Task,
    video_path: str,
    platform: str,
    project_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Optimize video for specific platform
    
    Priority: Normal
    Queue: video
    Timeout: 15 minutes
    """
    
    task_id = self.request.id
    
    try:
        self.update_progress(task_id, 0, "optimizing_video")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                video_service.optimize_for_platform(
                    Path(video_path),
                    platform
                )
            )
            
            self.update_progress(task_id, 100, "completed")
            
            return result
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Video optimization failed: {e}")
        raise self.retry(exc=e)

# ============================================================================
# CHAINED TASKS (WORKFLOWS)
# ============================================================================

@shared_task(bind=True, name="complete_video_workflow")
def complete_video_workflow_task(
    self: Task,
    project_id: int,
    voice_id: str = "rachel",
    video_settings: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Complete workflow: Content → TTS → Video
    
    This creates a chain of tasks that execute sequentially
    """
    
    task_id = self.request.id
    
    try:
        # Get project data
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            project_data = loop.run_until_complete(
                get_project_for_workflow(project_id)
            )
            
            if not project_data["script"]:
                raise ValueError("Project has no script")
            
            # Create task chain
            workflow = chain(
                # Generate TTS
                generate_tts_task.signature(
                    args=[
                        project_id,
                        project_data["script"],
                        voice_id
                    ],
                    priority=8
                ),
                
                # Generate video (will use the audio from previous task)
                generate_video_task.signature(
                    args=[project_id],
                    kwargs={"settings": video_settings or {}},
                    priority=7
                )
            )
            
            # Execute workflow
            result = workflow.apply_async()
            
            return {
                "workflow_id": result.id,
                "project_id": project_id,
                "status": "started",
                "steps": ["tts", "video"]
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        raise

# ============================================================================
# CLEANUP TASKS
# ============================================================================

@shared_task(name="cleanup_temp_files")
def cleanup_temp_files_task():
    """
    Clean up temporary files older than 24 hours
    
    Scheduled task that runs hourly
    """
    
    try:
        temp_dir = Path("/tmp/reels_generator")
        if not temp_dir.exists():
            return
        
        now = datetime.now()
        files_deleted = 0
        
        for file_path in temp_dir.rglob("*"):
            if file_path.is_file():
                # Check file age
                file_age = now - datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if file_age > timedelta(hours=24):
                    try:
                        file_path.unlink()
                        files_deleted += 1
                    except Exception as e:
                        logger.error(f"Failed to delete {file_path}: {e}")
        
        logger.info(f"Cleaned up {files_deleted} temporary files")
        
        return {"files_deleted": files_deleted}
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        raise

@shared_task(name="cleanup_failed_videos")
def cleanup_failed_videos_task():
    """
    Clean up videos from failed projects
    
    Scheduled task that runs daily
    """
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Get failed projects older than 7 days
            failed_projects = loop.run_until_complete(
                get_old_failed_projects(days=7)
            )
            
            cleaned = 0
            
            for project in failed_projects:
                # Delete associated files
                if project.get("video_file_path"):
                    try:
                        loop.run_until_complete(
                            storage_service.delete_file(project["video_file_path"])
                        )
                        cleaned += 1
                    except Exception as e:
                        logger.error(f"Failed to delete video: {e}")
            
            logger.info(f"Cleaned up {cleaned} failed video files")
            
            return {"cleaned": cleaned}
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Failed video cleanup failed: {e}")
        raise

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def update_project_status(
    project_id: int,
    status: ProjectStatus,
    error_message: Optional[str] = None
):
    """Update project status in database"""
    
    async with AsyncSessionLocal() as db:
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        if status == ProjectStatus.PROCESSING:
            update_data["processing_started_at"] = datetime.utcnow()
        elif status == ProjectStatus.COMPLETED:
            update_data["processing_completed_at"] = datetime.utcnow()
        elif status == ProjectStatus.FAILED:
            update_data["error_message"] = error_message
        
        await db.execute(
            update(Project)
            .where(Project.id == project_id)
            .values(**update_data)
        )
        await db.commit()

async def update_project_audio(
    project_id: int,
    audio_url: str,
    voice_id: str
):
    """Update project with audio data"""
    
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Project)
            .where(Project.id == project_id)
            .values(
                audio_file_path=audio_url,
                voice_id=voice_id,
                updated_at=datetime.utcnow()
            )
        )
        await db.commit()

async def update_project_video(
    project_id: int,
    video_url: str,
    thumbnail_url: str,
    metadata: Dict[str, Any]
):
    """Update project with video data"""
    
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Project)
            .where(Project.id == project_id)
            .values(
                video_file_path=video_url,
                thumbnail_path=thumbnail_url,
                status=ProjectStatus.COMPLETED,
                processing_completed_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )
        await db.commit()

async def get_project_for_video(project_id: int) -> Dict[str, Any]:
    """Get project data for video generation"""
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Project).where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()
        
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        return {
            "audio_url": project.audio_file_path,
            "script": project.script
        }

async def get_project_for_workflow(project_id: int) -> Dict[str, Any]:
    """Get project data for workflow"""
    
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

async def get_old_failed_projects(days: int) -> List[Dict[str, Any]]:
    """Get failed projects older than specified days"""
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Project).where(
                Project.status == ProjectStatus.FAILED,
                Project.updated_at < cutoff_date
            )
        )
        projects = result.scalars().all()
        
        return [
            {
                "id": p.id,
                "video_file_path": p.video_file_path,
                "audio_file_path": p.audio_file_path
            }
            for p in projects
        ]
