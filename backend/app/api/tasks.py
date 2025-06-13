# backend/app/api/tasks.py
"""
⚡ REELS GENERATOR - Task Management API
Week 6: Endpoints for Celery task management and monitoring
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from ..api.auth import get_current_active_user
from ..models import User, UserRole
from ..tasks.celery_app import celery_app, task_monitor, submit_priority_task, get_batch_status
from ..tasks.content_tasks import generate_content_task, batch_generate_content_task
from ..tasks.video_tasks import generate_video_task, generate_advanced_video_task, complete_video_workflow_task
from ..tasks.monitoring import (
    check_failed_tasks,
    requeue_failed_tasks,
    cleanup_stuck_tasks,
    ping_workers,
    scale_workers
)

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# ============================================================================
# TASK STATUS ENDPOINTS
# ============================================================================

@router.get("/status/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get detailed status of a specific task
    
    Returns task state, progress, result, and execution metrics
    """
    
    try:
        status = task_monitor.get_task_status(task_id)
        
        if not status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve task status"
        )

@router.get("/batch/{batch_id}")
async def get_batch_task_status(
    batch_id: str,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get status of a batch job
    
    Returns overall progress and individual task statuses
    """
    
    try:
        status = get_batch_status(batch_id)
        
        if "error" in status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=status["error"]
            )
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get batch status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve batch status"
        )

# ============================================================================
# TASK SUBMISSION ENDPOINTS
# ============================================================================

@router.post("/submit/content")
async def submit_content_task(
    project_id: int,
    topic: str,
    target_audience: str,
    video_style: str = "educational",
    duration: int = 60,
    priority: int = Query(5, ge=0, le=10),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Submit content generation task
    
    Priority: 0 (lowest) to 10 (highest)
    """
    
    try:
        task = submit_priority_task(
            "generate_content",
            args=(project_id, topic, target_audience, video_style, duration),
            kwargs={},
            priority=priority,
            queue="content"
        )
        
        return {
            "task_id": task.id,
            "status": "submitted",
            "queue": "content",
            "priority": priority
        }
        
    except Exception as e:
        logger.error(f"Failed to submit content task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit task"
        )

@router.post("/submit/video")
async def submit_video_task(
    project_id: int,
    audio_url: str,
    script: str,
    settings: Dict[str, Any],
    advanced: bool = False,
    priority: int = Query(5, ge=0, le=10),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Submit video generation task
    
    Set advanced=true for advanced video processing with effects
    """
    
    try:
        # Determine task and queue
        if advanced:
            task_name = "generate_advanced_video"
            queue = "gpu" if settings.get("quality") == "ultra" else "video"
        else:
            task_name = "generate_video"
            queue = "video"
        
        task = submit_priority_task(
            task_name,
            args=(project_id, audio_url, script, settings),
            kwargs={},
            priority=priority,
            queue=queue
        )
        
        return {
            "task_id": task.id,
            "status": "submitted",
            "queue": queue,
            "priority": priority,
            "type": "advanced" if advanced else "basic"
        }
        
    except Exception as e:
        logger.error(f"Failed to submit video task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit task"
        )

@router.post("/submit/workflow")
async def submit_workflow_task(
    project_id: int,
    voice_id: str = "rachel",
    video_settings: Optional[Dict[str, Any]] = None,
    priority: int = Query(7, ge=0, le=10),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Submit complete workflow: Content → TTS → Video
    
    This creates a chain of dependent tasks
    """
    
    try:
        task = complete_video_workflow_task.apply_async(
            args=[project_id, voice_id, video_settings or {}],
            priority=priority
        )
        
        return {
            "workflow_id": task.id,
            "status": "submitted",
            "priority": priority,
            "steps": ["content", "tts", "video"]
        }
        
    except Exception as e:
        logger.error(f"Failed to submit workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit workflow"
        )

@router.post("/submit/batch")
async def submit_batch_tasks(
    task_type: str,
    items: List[Dict[str, Any]],
    priority: int = Query(3, ge=0, le=10),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Submit batch of similar tasks
    
    task_type: content, video, or tts
    """
    
    if len(items) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 items per batch"
        )
    
    try:
        if task_type == "content":
            # Create batch content generation
            project_ids = [item["project_id"] for item in items]
            settings = items[0].get("settings", {})
            
            task = batch_generate_content_task.apply_async(
                args=[project_ids, current_user.id, settings],
                priority=priority
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported batch type: {task_type}"
            )
        
        return {
            "batch_id": task.id,
            "status": "submitted",
            "task_type": task_type,
            "item_count": len(items),
            "priority": priority
        }
        
    except Exception as e:
        logger.error(f"Failed to submit batch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit batch"
        )

# ============================================================================
# TASK CONTROL ENDPOINTS
# ============================================================================

@router.post("/cancel/{task_id}")
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Cancel a running or pending task
    """
    
    try:
        result = celery_app.AsyncResult(task_id)
        
        if result.state in ["PENDING", "STARTED"]:
            result.revoke(terminate=True)
            
            return {
                "task_id": task_id,
                "status": "cancelled",
                "previous_state": result.state
            }
        else:
            return {
                "task_id": task_id,
                "status": "not_cancellable",
                "current_state": result.state
            }
            
    except Exception as e:
        logger.error(f"Failed to cancel task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel task"
        )

@router.post("/retry/{task_id}")
async def retry_failed_task(
    task_id: str,
    countdown: int = Query(60, ge=0, le=3600),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Retry a failed task
    
    countdown: Delay in seconds before retry (default: 60s)
    """
    
    try:
        result = celery_app.AsyncResult(task_id)
        
        if result.state != "FAILURE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only retry failed tasks"
            )
        
        # Get task info
        task_name = result.name
        args = result.args
        kwargs = result.kwargs
        
        # Resubmit task
        new_task = celery_app.send_task(
            task_name,
            args=args,
            kwargs=kwargs,
            countdown=countdown
        )
        
        return {
            "original_task_id": task_id,
            "new_task_id": new_task.id,
            "status": "resubmitted",
            "countdown": countdown
        }
        
    except Exception as e:
        logger.error(f"Failed to retry task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry task"
        )

# ============================================================================
# MONITORING ENDPOINTS
# ============================================================================

@router.get("/stats/queues")
async def get_queue_statistics(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get current queue statistics
    
    Shows pending, active, completed, and failed tasks per queue
    """
    
    try:
        stats = task_monitor.get_queue_stats()
        
        # Add queue health indicators
        for queue_name, queue_stats in stats.items():
            pending = queue_stats["pending"]
            active = queue_stats["active"]
            
            # Determine health status
            if pending > 100:
                health = "critical"
            elif pending > 50:
                health = "warning"
            else:
                health = "healthy"
            
            queue_stats["health"] = health
            queue_stats["backlog_minutes"] = pending * 2  # Rough estimate
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "queues": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve queue statistics"
        )

@router.get("/stats/workers")
async def get_worker_statistics(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get worker statistics and health
    """
    
    try:
        stats = task_monitor.get_worker_stats()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "workers": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get worker stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve worker statistics"
        )

@router.get("/stats/performance")
async def get_performance_metrics(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get task performance metrics
    """
    
    try:
        # Run monitoring task
        result = await monitor_task_performance.apply_async()
        performance_data = result.get(timeout=10)
        
        return performance_data
        
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve performance metrics"
        )

# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.post("/admin/cleanup", dependencies=[Depends(get_current_active_user)])
async def cleanup_tasks(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Clean up stuck tasks (Admin only)
    """
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        result = cleanup_stuck_tasks.apply_async()
        cleanup_result = result.get(timeout=30)
        
        return cleanup_result
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cleanup operation failed"
        )

@router.post("/admin/requeue", dependencies=[Depends(get_current_active_user)])
async def requeue_tasks(
    max_age_hours: int = Query(24, ge=1, le=168),
    max_retries: int = Query(3, ge=1, le=5),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Requeue failed tasks (Admin only)
    """
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        result = requeue_failed_tasks.apply_async(
            args=[max_age_hours, max_retries]
        )
        requeue_result = result.get(timeout=30)
        
        return requeue_result
        
    except Exception as e:
        logger.error(f"Requeue failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Requeue operation failed"
        )

@router.post("/admin/scale", dependencies=[Depends(get_current_active_user)])
async def scale_queue_workers(
    queue_name: str,
    desired_workers: int = Query(..., ge=0, le=20),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Scale workers for a specific queue (Admin only)
    """
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    valid_queues = ["content", "video", "gpu", "social", "celery"]
    if queue_name not in valid_queues:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid queue. Must be one of: {valid_queues}"
        )
    
    try:
        result = scale_workers.apply_async(
            args=[queue_name, desired_workers]
        )
        scale_result = result.get(timeout=10)
        
        return scale_result
        
    except Exception as e:
        logger.error(f"Scaling failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Scaling operation failed"
        )

# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@router.get("/health")
async def celery_health_check() -> Dict[str, Any]:
    """
    Check Celery system health
    """
    
    try:
        # Ping workers
        ping_result = ping_workers.apply_async()
        worker_status = ping_result.get(timeout=5)
        
        # Get queue stats
        queue_stats = task_monitor.get_queue_stats()
        
        # Calculate overall health
        total_pending = sum(q["pending"] for q in queue_stats.values())
        total_active = sum(q["active"] for q in queue_stats.values())
        
        if not worker_status["workers"]:
            health = "critical"
            message = "No workers available"
        elif total_pending > 500:
            health = "warning"
            message = "High queue backlog"
        else:
            health = "healthy"
            message = "System operational"
        
        return {
            "health": health,
            "message": message,
            "metrics": {
                "workers": len(worker_status["workers"]),
                "total_pending": total_pending,
                "total_active": total_active
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "health": "critical",
            "message": f"Health check failed: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }
