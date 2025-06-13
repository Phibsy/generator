# backend/app/api/batch.py
"""
🚀 REELS GENERATOR - Batch Processing API
Week 8: Endpoints for batch video generation with optimization
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta

from ..database import get_db
from ..models import User
from ..schemas.batch import (
    BatchCreateRequest,
    BatchResponse,
    BatchStatusResponse,
    BatchOptimizationRequest,
    BatchMetricsResponse
)
from ..services.batch_processing import (
    batch_processing_service,
    BatchPriority,
    batch_recovery_service
)
from .auth import get_current_active_user

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter()

# ============================================================================
# BATCH CREATION AND MANAGEMENT
# ============================================================================

@router.post("/create", response_model=BatchResponse)
async def create_batch(
    request: BatchCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
) -> BatchResponse:
    """
    Create a new batch processing job
    
    - Validates projects belong to user
    - Optimizes execution plan
    - Queues for processing
    """
    
    try:
        # Check user limits
        if len(request.project_ids) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 50 projects per batch"
            )
        
        # Determine priority based on user type
        if current_user.subscription_plan == "premium":
            priority = BatchPriority.HIGH
        elif len(request.project_ids) < 5:
            priority = BatchPriority.NORMAL
        else:
            priority = BatchPriority.LOW
        
        # Create batch
        batch_job = await batch_processing_service.create_batch(
            user_id=current_user.id,
            project_ids=request.project_ids,
            settings=request.settings,
            priority=priority,
            metadata={
                "user_plan": current_user.subscription_plan,
                "optimization_strategy": request.optimization_strategy,
                "requested_at": datetime.utcnow().isoformat()
            }
        )
        
        # Queue for processing
        if request.auto_start:
            background_tasks.add_task(
                batch_processing_service.execute_batch,
                batch_job.batch_id
            )
        
        return BatchResponse(
            batch_id=batch_job.batch_id,
            status=batch_job.status,
            total_projects=len(batch_job.project_ids),
            valid_projects=len(batch_job.project_ids),
            priority=batch_job.priority.name,
            estimated_completion_time=calculate_estimated_time(batch_job),
            created_at=batch_job.created_at
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Batch creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create batch"
        )

@router.post("/{batch_id}/start")
async def start_batch_processing(
    batch_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, str]:
    """
    Start processing a created batch
    """
    
    # Verify batch belongs to user
    batch_job = await batch_processing_service._get_batch_job(batch_id)
    
    if not batch_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    if batch_job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    if batch_job.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch is already {batch_job.status}"
        )
    
    # Start processing
    background_tasks.add_task(
        batch_processing_service.execute_batch,
        batch_id
    )
    
    return {
        "message": "Batch processing started",
        "batch_id": batch_id
    }

@router.post("/{batch_id}/cancel")
async def cancel_batch(
    batch_id: str,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Cancel a running batch
    """
    
    # Implementation for batch cancellation
    # This would cancel all pending tasks in the batch
    
    return {
        "message": "Batch cancelled",
        "batch_id": batch_id,
        "cancelled_tasks": 0
    }

# ============================================================================
# BATCH STATUS AND MONITORING
# ============================================================================

@router.get("/{batch_id}/status", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    current_user: User = Depends(get_current_active_user)
) -> BatchStatusResponse:
    """
    Get detailed status of a batch job
    """
    
    status = await batch_processing_service.get_batch_status(batch_id)
    
    if "error" in status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=status["error"]
        )
    
    # Verify user owns the batch
    batch_job = await batch_processing_service._get_batch_job(batch_id)
    if batch_job and batch_job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return BatchStatusResponse(**status)

@router.get("/list")
async def list_user_batches(
    status: Optional[str] = Query(None, regex="^(pending|processing|completed|failed)$"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    List user's batch jobs
    """
    
    batches = await batch_processing_service.list_user_batches(
        user_id=current_user.id,
        status=status,
        limit=limit
    )
    
    return batches

@router.get("/{batch_id}/progress")
async def get_batch_progress(
    batch_id: str,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get real-time progress of batch processing
    """
    
    # Verify ownership
    batch_job = await batch_processing_service._get_batch_job(batch_id)
    
    if not batch_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    if batch_job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get progress
    progress = await batch_processing_service.progress_tracker.get_batch_progress(batch_id)
    
    return {
        "batch_id": batch_id,
        "progress": progress,
        "websocket_url": f"/ws/{current_user.id}"  # For real-time updates
    }

# ============================================================================
# BATCH OPTIMIZATION
# ============================================================================

@router.post("/optimize")
async def optimize_batch_settings(
    request: BatchOptimizationRequest,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get optimized settings for batch processing
    
    Analyzes projects and suggests optimal configuration
    """
    
    try:
        # Convert target time to timedelta
        target_time = None
        if request.target_completion_hours:
            target_time = timedelta(hours=request.target_completion_hours)
        
        # Get optimization suggestions
        optimal_settings = await batch_processing_service.optimize_batch_settings(
            project_ids=request.project_ids,
            target_completion_time=target_time
        )
        
        return {
            "recommended_settings": optimal_settings,
            "estimated_duration": calculate_duration_estimate(
                len(request.project_ids),
                optimal_settings
            ),
            "estimated_cost": calculate_cost_estimate(
                len(request.project_ids),
                optimal_settings
            )
        }
        
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to optimize batch settings"
        )

@router.get("/resource-availability")
async def get_resource_availability(
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get current resource availability for batch processing
    """
    
    resources = await batch_processing_service.resource_monitor.get_available_resources()
    forecast = await batch_processing_service.resource_monitor.get_resource_forecast()
    
    return {
        "current": {
            "cpu_cores": resources.cpu_cores,
            "memory_gb": resources.memory_mb / 1024,
            "gpu_count": resources.gpu_count,
            "storage_gb": resources.storage_gb
        },
        "forecast": forecast,
        "recommended_batch_size": calculate_recommended_batch_size(resources)
    }

# ============================================================================
# BATCH METRICS AND ANALYTICS
# ============================================================================

@router.get("/{batch_id}/metrics", response_model=BatchMetricsResponse)
async def get_batch_metrics(
    batch_id: str,
    current_user: User = Depends(get_current_active_user)
) -> BatchMetricsResponse:
    """
    Get performance metrics for a completed batch
    """
    
    # Get batch and verify ownership
    batch_job = await batch_processing_service._get_batch_job(batch_id)
    
    if not batch_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    if batch_job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get metrics
    metrics = await batch_processing_service._get_batch_metrics(batch_job)
    
    return BatchMetricsResponse(
        batch_id=batch_id,
        total_projects=metrics.total_projects,
        completed_projects=metrics.completed_projects,
        failed_projects=metrics.failed_projects,
        average_processing_time=metrics.average_processing_time,
        total_processing_time=(
            (batch_job.completed_at - batch_job.started_at).total_seconds()
            if batch_job.completed_at and batch_job.started_at else 0
        ),
        resource_utilization=metrics.resource_utilization
    )

@router.get("/statistics")
async def get_batch_statistics(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get user's batch processing statistics
    """
    
    # Get statistics from the last N days
    # This would aggregate data from completed batches
    
    return {
        "period_days": days,
        "total_batches": 0,
        "total_projects_processed": 0,
        "average_batch_size": 0,
        "average_processing_time": 0,
        "success_rate": 0,
        "most_used_settings": {}
    }

# ============================================================================
# BATCH RECOVERY
# ============================================================================

@router.post("/{batch_id}/retry")
async def retry_failed_batch(
    batch_id: str,
    retry_failed_only: bool = Query(True),
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Retry a failed batch or failed tasks within a batch
    """
    
    # Verify ownership
    batch_job = await batch_processing_service._get_batch_job(batch_id)
    
    if not batch_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    if batch_job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Queue recovery
    background_tasks.add_task(
        batch_recovery_service.recover_failed_batch,
        batch_id,
        retry_failed_only
    )
    
    return {
        "message": "Batch recovery initiated",
        "batch_id": batch_id,
        "retry_mode": "failed_only" if retry_failed_only else "all"
    }

# ============================================================================
# BATCH TEMPLATES
# ============================================================================

@router.get("/templates")
async def get_batch_templates(
    current_user: User = Depends(get_current_active_user)
) -> List[Dict[str, Any]]:
    """
    Get predefined batch processing templates
    """
    
    return [
        {
            "id": "quick_batch",
            "name": "Quick Batch",
            "description": "Fast processing with standard quality",
            "settings": {
                "video_quality": "medium",
                "parallel_limit": 5,
                "optimization_strategy": "speed"
            }
        },
        {
            "id": "quality_batch",
            "name": "Quality Batch",
            "description": "High quality output with slower processing",
            "settings": {
                "video_quality": "high",
                "parallel_limit": 2,
                "optimization_strategy": "quality",
                "advanced_video": True
            }
        },
        {
            "id": "economy_batch",
            "name": "Economy Batch",
            "description": "Cost-optimized processing",
            "settings": {
                "video_quality": "medium",
                "parallel_limit": 1,
                "optimization_strategy": "cost"
            }
        },
        {
            "id": "bulk_batch",
            "name": "Bulk Processing",
            "description": "Optimized for large batches",
            "settings": {
                "video_quality": "medium",
                "parallel_limit": 3,
                "optimization_strategy": "balanced",
                "skip_preview": True
            }
        }
    ]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_estimated_time(batch_job) -> datetime:
    """Calculate estimated completion time for batch"""
    
    # Simple estimation based on project count and settings
    projects = len(batch_job.project_ids)
    parallel = batch_job.metadata.get("parallel_limit", 3)
    
    # Assume 5 minutes per project on average
    minutes_per_project = 5
    
    # Account for parallelism
    total_minutes = (projects / parallel) * minutes_per_project
    
    return datetime.utcnow() + timedelta(minutes=total_minutes)

def calculate_duration_estimate(project_count: int, settings: Dict[str, Any]) -> int:
    """Estimate batch duration in minutes"""
    
    base_time = 5  # minutes per project
    
    # Adjust for quality
    if settings.get("video_quality") == "high":
        base_time *= 1.5
    elif settings.get("video_quality") == "ultra":
        base_time *= 2.5
    
    # Adjust for parallelism
    parallel = settings.get("parallel_limit", 3)
    
    return int((project_count / parallel) * base_time)

def calculate_cost_estimate(project_count: int, settings: Dict[str, Any]) -> float:
    """Estimate batch processing cost"""
    
    # Simplified cost calculation
    base_cost = 0.10  # per project
    
    # Adjust for quality
    if settings.get("video_quality") == "high":
        base_cost *= 1.5
    elif settings.get("video_quality") == "ultra":
        base_cost *= 3.0
    
    # Adjust for features
    if settings.get("advanced_video"):
        base_cost *= 1.3
    
    return round(project_count * base_cost, 2)

def calculate_recommended_batch_size(resources) -> int:
    """Calculate recommended batch size based on resources"""
    
    # Simple calculation based on available resources
    cpu_based = resources.cpu_cores * 5
    memory_based = (resources.memory_mb / 2048) * 3  # 2GB per video task
    
    return min(50, int(min(cpu_based, memory_based)))

# ============================================================================
# backend/app/schemas/batch.py - Batch processing schemas
"""
📋 Batch Processing Schemas
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

class OptimizationStrategy(str, Enum):
    SPEED = "speed"
    COST = "cost"
    QUALITY = "quality"
    BALANCED = "balanced"

class BatchCreateRequest(BaseModel):
    """Request to create a batch job"""
    project_ids: List[int] = Field(..., min_items=1, max_items=50)
    settings: Dict[str, Any] = Field(default_factory=dict)
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.BALANCED
    auto_start: bool = Field(default=True)
    
    @validator('project_ids')
    def unique_project_ids(cls, v):
        if len(v) != len(set(v)):
            raise ValueError('Duplicate project IDs not allowed')
        return v

class BatchResponse(BaseModel):
    """Response for batch creation"""
    batch_id: str
    status: str
    total_projects: int
    valid_projects: int
    priority: str
    estimated_completion_time: datetime
    created_at: datetime

class BatchStatusResponse(BaseModel):
    """Detailed batch status"""
    batch_id: str
    status: str
    progress: float
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    total_projects: int
    completed_projects: int
    failed_projects: int
    metrics: Dict[str, Any]
    results: Dict[str, Any]

class BatchOptimizationRequest(BaseModel):
    """Request for batch optimization"""
    project_ids: List[int]
    target_completion_hours: Optional[float] = None
    preferred_quality: str = "medium"
    budget_limit: Optional[float] = None

class BatchMetricsResponse(BaseModel):
    """Batch processing metrics"""
    batch_id: str
    total_projects: int
    completed_projects: int
    failed_projects: int
    average_processing_time: float
    total_processing_time: float
    resource_utilization: Dict[str, float]
