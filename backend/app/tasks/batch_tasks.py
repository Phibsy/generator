# backend/app/tasks/batch_tasks.py
"""
🚀 REELS GENERATOR - Batch Processing Tasks
Week 8: Celery tasks for optimized batch video generation
"""

from celery import shared_task, Task, group, chord, chain
from celery.result import allow_join_result
from typing import Dict, Any, List, Tuple, Optional
import logging
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
import json
import redis

from ..services.batch_processing import (
    batch_processing_service,
    BatchJob,
    BatchPriority,
    ProcessingMetrics
)
from ..database import AsyncSessionLocal
from ..models import Project, ProjectStatus
from .celery_app import celery_app, task_monitor
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

# ============================================================================
# MAIN BATCH PROCESSING TASK
# ============================================================================

@shared_task(
    bind=True,
    name="process_batch",
    queue="batch",
    max_retries=2,
    soft_time_limit=14400,  # 4 hours
    time_limit=18000  # 5 hours
)
def process_batch_task(
    self: Task,
    batch_id: str
) -> Dict[str, Any]:
    """
    Main batch processing task
    
    Orchestrates the entire batch processing workflow
    """
    
    task_id = self.request.id
    logger.info(f"Starting batch processing task {task_id} for batch {batch_id}")
    
    try:
        self.update_progress(task_id, 0, "initializing")
        
        # Execute batch
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            results = loop.run_until_complete(
                batch_processing_service.execute_batch(batch_id)
            )
            
            self.update_progress(task_id, 100, "completed")
            
            logger.info(f"✅ Batch {batch_id} completed successfully")
            
            return results
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        self.update_progress(task_id, -1, "failed", {"error": str(e)})
        raise self.retry(exc=e)

# ============================================================================
# BATCH ORCHESTRATION TASKS
# ============================================================================

@shared_task(
    bind=True,
    name="orchestrate_batch_workflow",
    queue="batch",
    max_retries=1
)
def orchestrate_batch_workflow_task(
    self: Task,
    batch_id: str,
    execution_plan: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Orchestrate complex batch workflow with dependencies
    
    Handles task dependencies and parallel execution
    """
    
    task_id = self.request.id
    
    try:
        self.update_progress(task_id, 0, "planning_execution")
        
        # Group tasks by dependency level
        dependency_levels = _group_by_dependencies(execution_plan)
        
        results = {
            "successful": [],
            "failed": [],
            "task_results": {}
        }
        
        # Process each dependency level
        for level, tasks in enumerate(dependency_levels):
            progress = (level / len(dependency_levels)) * 100
            self.update_progress(
                task_id,
                progress,
                f"processing_level_{level}"
            )
            
            # Create parallel task group for this level
            if len(tasks) == 1:
                # Single task
                task_result = _execute_single_batch_task(tasks[0])
                results["task_results"][tasks[0]["project_id"]] = task_result
                
            else:
                # Multiple tasks in parallel
                task_group = group(
                    _execute_single_batch_task.s(task)
                    for task in tasks
                )
                
                # Execute and wait
                group_results = task_group.apply_async()
                
                # Collect results
                with allow_join_result():
                    for i, result in enumerate(group_results.get()):
                        results["task_results"][tasks[i]["project_id"]] = result
            
            # Check for failures
            level_failures = [
                t for t in tasks
                if results["task_results"][t["project_id"]].get("status") == "failed"
            ]
            
            if level_failures and level < len(dependency_levels) - 1:
                logger.warning(f"Failures in level {level}, but continuing...")
        
        self.update_progress(task_id, 100, "workflow_completed")
        
        return results
        
    except Exception as e:
        logger.error(f"Batch workflow orchestration failed: {e}")
        raise

# ============================================================================
# BATCH OPTIMIZATION TASKS
# ============================================================================

@shared_task(
    bind=True,
    name="optimize_batch_execution",
    queue="batch",
    max_retries=2
)
def optimize_batch_execution_task(
    self: Task,
    batch_id: str
) -> Dict[str, Any]:
    """
    Optimize batch execution based on resource availability
    
    Dynamically adjusts parallelism and resource allocation
    """
    
    task_id = self.request.id
    
    try:
        self.update_progress(task_id, 0, "analyzing_resources")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Get current resource usage
            resources = loop.run_until_complete(
                batch_processing_service.resource_monitor.get_available_resources()
            )
            
            self.update_progress(task_id, 30, "analyzing_batch")
            
            # Get batch details
            batch_job = loop.run_until_complete(
                batch_processing_service._get_batch_job(batch_id)
            )
            
            if not batch_job:
                raise ValueError(f"Batch {batch_id} not found")
            
            self.update_progress(task_id, 60, "calculating_optimization")
            
            # Calculate optimal settings
            optimal_settings = loop.run_until_complete(
                batch_processing_service.optimize_batch_settings(
                    batch_job.project_ids,
                    target_completion_time=timedelta(hours=2)
                )
            )
            
            # Apply optimizations
            batch_job.metadata.update(optimal_settings)
            batch_job.parallel_limit = optimal_settings.get("parallel_limit", 3)
            
            loop.run_until_complete(
                batch_processing_service._update_batch_job(batch_job)
            )
            
            self.update_progress(task_id, 100, "optimization_complete")
            
            return {
                "batch_id": batch_id,
                "original_settings": batch_job.settings,
                "optimized_settings": optimal_settings,
                "estimated_speedup": calculate_speedup(batch_job.settings, optimal_settings)
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Batch optimization failed: {e}")
        raise self.retry(exc=e)

# ============================================================================
# BATCH RECOVERY TASKS
# ============================================================================

@shared_task(
    bind=True,
    name="recover_failed_batch",
    queue="batch",
    max_retries=1
)
def recover_failed_batch_task(
    self: Task,
    batch_id: str,
    retry_failed_only: bool = True
) -> Dict[str, Any]:
    """
    Recover failed batch by retrying failed tasks
    """
    
    task_id = self.request.id
    
    try:
        self.update_progress(task_id, 0, "loading_batch")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            batch_job = loop.run_until_complete(
                batch_processing_service._get_batch_job(batch_id)
            )
            
            if not batch_job:
                raise ValueError(f"Batch {batch_id} not found")
            
            self.update_progress(task_id, 20, "identifying_failures")
            
            # Identify failed tasks
            failed_projects = []
            if batch_job.results:
                failed_projects = [
                    item["project_id"] 
                    for item in batch_job.results.get("failed", [])
                ]
            
            if not failed_projects and retry_failed_only:
                return {
                    "batch_id": batch_id,
                    "status": "no_failures",
                    "message": "No failed tasks to retry"
                }
            
            self.update_progress(task_id, 40, "creating_recovery_batch")
            
            # Create recovery batch
            recovery_projects = failed_projects if retry_failed_only else batch_job.project_ids
            
            recovery_batch = loop.run_until_complete(
                batch_processing_service.create_batch(
                    user_id=batch_job.user_id,
                    project_ids=recovery_projects,
                    settings=batch_job.settings,
                    priority=BatchPriority.HIGH,
                    metadata={
                        "original_batch": batch_id,
                        "recovery_attempt": 1,
                        "retry_failed_only": retry_failed_only
                    }
                )
            )
            
            self.update_progress(task_id, 80, "executing_recovery")
            
            # Execute recovery batch
            loop.run_until_complete(
                batch_processing_service.execute_batch(recovery_batch.batch_id)
            )
            
            self.update_progress(task_id, 100, "recovery_complete")
            
            return {
                "original_batch_id": batch_id,
                "recovery_batch_id": recovery_batch.batch_id,
                "recovered_projects": len(recovery_projects),
                "status": "completed"
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Batch recovery failed: {e}")
        raise

# ============================================================================
# BATCH MONITORING TASKS
# ============================================================================

@shared_task(
    name="monitor_batch_health",
    queue="celery"
)
def monitor_batch_health_task() -> Dict[str, Any]:
    """
    Monitor health of all active batches
    
    Scheduled task that runs every 5 minutes
    """
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Get all active batches
            active_batches = loop.run_until_complete(
                get_active_batches()
            )
            
            health_report = {
                "timestamp": datetime.utcnow().isoformat(),
                "total_active": len(active_batches),
                "healthy": 0,
                "warning": 0,
                "critical": 0,
                "batches": []
            }
            
            for batch in active_batches:
                batch_health = loop.run_until_complete(
                    assess_batch_health(batch)
                )
                
                health_report["batches"].append(batch_health)
                health_report[batch_health["status"]] += 1
            
            # Send alerts for critical batches
            critical_batches = [
                b for b in health_report["batches"] 
                if b["status"] == "critical"
            ]
            
            if critical_batches:
                loop.run_until_complete(
                    send_batch_alerts(critical_batches)
                )
            
            return health_report
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Batch health monitoring failed: {e}")
        raise

@shared_task(
    name="generate_batch_report",
    queue="celery"
)
def generate_batch_report_task(
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Any]:
    """
    Generate comprehensive batch processing report
    """
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Collect batch metrics
            metrics = loop.run_until_complete(
                collect_batch_metrics(start_date, end_date)
            )
            
            report = {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "summary": {
                    "total_batches": metrics["total_batches"],
                    "total_projects": metrics["total_projects"],
                    "success_rate": metrics["success_rate"],
                    "average_duration": metrics["avg_duration"],
                    "average_batch_size": metrics["avg_batch_size"]
                },
                "performance": {
                    "fastest_batch": metrics["fastest_batch"],
                    "slowest_batch": metrics["slowest_batch"],
                    "peak_concurrent": metrics["peak_concurrent"]
                },
                "resource_usage": {
                    "cpu_utilization": metrics["cpu_utilization"],
                    "memory_utilization": metrics["memory_utilization"],
                    "gpu_utilization": metrics["gpu_utilization"]
                },
                "failures": {
                    "total_failures": metrics["total_failures"],
                    "failure_reasons": metrics["failure_reasons"],
                    "recovery_success_rate": metrics["recovery_rate"]
                }
            }
            
            # Store report
            loop.run_until_complete(
                store_batch_report(report)
            )
            
            return report
            
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Batch report generation failed: {e}")
        raise

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _execute_single_batch_task(task_config: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a single task in the batch"""
    
    try:
        # Import the appropriate task
        if task_config["task_type"] == "content":
            from .content_tasks import generate_content_task as task_func
        elif task_config["task_type"] == "video":
            from .video_tasks import generate_video_task as task_func
        elif task_config["task_type"] == "advanced_video":
            from .video_tasks import generate_advanced_video_task as task_func
        else:
            raise ValueError(f"Unknown task type: {task_config['task_type']}")
        
        # Execute task
        result = task_func.apply_async(
            args=task_config.get("args", []),
            kwargs=task_config.get("kwargs", {}),
            priority=task_config.get("priority", 5)
        )
        
        # Wait for completion
        task_result = result.get(timeout=task_config.get("timeout", 3600))
        
        return {
            "status": "success",
            "project_id": task_config["project_id"],
            "result": task_result
        }
        
    except Exception as e:
        logger.error(f"Task execution failed: {e}")
        return {
            "status": "failed",
            "project_id": task_config["project_id"],
            "error": str(e)
        }

def _group_by_dependencies(execution_plan: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Group tasks by dependency levels"""
    
    # Simple dependency resolution
    levels = []
    remaining = execution_plan.copy()
    
    while remaining:
        # Find tasks with no dependencies or dependencies in previous levels
        current_level = []
        completed_ids = [task["project_id"] for level in levels for task in level]
        
        for task in remaining[:]:
            deps = task.get("dependencies", [])
            if all(dep in completed_ids for dep in deps):
                current_level.append(task)
                remaining.remove(task)
        
        if current_level:
            levels.append(current_level)
        else:
            # Circular dependency or error
            logger.error(f"Could not resolve dependencies for: {remaining}")
            break
    
    return levels

def calculate_speedup(original: Dict[str, Any], optimized: Dict[str, Any]) -> float:
    """Calculate estimated speedup from optimization"""
    
    original_parallel = original.get("parallel_limit", 1)
    optimized_parallel = optimized.get("parallel_limit", 1)
    
    # Simple speedup calculation
    speedup = optimized_parallel / original_parallel
    
    # Adjust for quality differences
    if original.get("video_quality") != optimized.get("video_quality"):
        quality_factor = {
            "low": 0.5,
            "medium": 1.0,
            "high": 1.5,
            "ultra": 2.5
        }
        
        original_factor = quality_factor.get(original.get("video_quality", "medium"), 1.0)
        optimized_factor = quality_factor.get(optimized.get("video_quality", "medium"), 1.0)
        
        speedup *= (original_factor / optimized_factor)
    
    return round(speedup, 2)

async def get_active_batches() -> List[Dict[str, Any]]:
    """Get all currently active batches"""
    
    # Implementation would query Redis for active batches
    return []

async def assess_batch_health(batch: Dict[str, Any]) -> Dict[str, Any]:
    """Assess health of a batch"""
    
    # Implementation would check batch progress and resource usage
    return {
        "batch_id": batch["batch_id"],
        "status": "healthy",
        "progress": batch.get("progress", 0),
        "issues": []
    }

async def send_batch_alerts(critical_batches: List[Dict[str, Any]]):
    """Send alerts for critical batches"""
    
    # Implementation would send notifications
    pass

async def collect_batch_metrics(
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Any]:
    """Collect batch processing metrics"""
    
    # Implementation would aggregate metrics from database
    return {
        "total_batches": 0,
        "total_projects": 0,
        "success_rate": 0.0,
        "avg_duration": 0.0,
        "avg_batch_size": 0.0,
        "fastest_batch": None,
        "slowest_batch": None,
        "peak_concurrent": 0,
        "cpu_utilization": 0.0,
        "memory_utilization": 0.0,
        "gpu_utilization": 0.0,
        "total_failures": 0,
        "failure_reasons": {},
        "recovery_rate": 0.0
    }

async def store_batch_report(report: Dict[str, Any]):
    """Store batch report in database"""
    
    # Implementation would save report
    pass
