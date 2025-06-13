# backend/app/services/batch_processing.py
"""
🚀 REELS GENERATOR - Batch Processing Service
Week 8: Optimized batch video generation with resource management
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
from collections import defaultdict
import psutil
import json

from ..config import settings
from ..database import AsyncSessionLocal
from ..models import Project, ProjectStatus, User
from ..tasks.celery_app import celery_app, submit_priority_task
from ..services.websocket_manager import manager
from sqlalchemy import select, update, and_
import redis.asyncio as redis

logger = logging.getLogger(__name__)

# ============================================================================
# DATA STRUCTURES
# ============================================================================

class BatchPriority(Enum):
    """Batch processing priority levels"""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    URGENT = 10

class ResourceType(Enum):
    """System resource types"""
    CPU = "cpu"
    MEMORY = "memory"
    GPU = "gpu"
    STORAGE = "storage"

@dataclass
class BatchJob:
    """Batch job configuration"""
    batch_id: str
    user_id: int
    project_ids: List[int]
    settings: Dict[str, Any]
    priority: BatchPriority = BatchPriority.NORMAL
    parallel_limit: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    progress: float = 0.0
    results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ResourceAllocation:
    """Resource allocation for batch processing"""
    cpu_cores: int
    memory_mb: int
    gpu_count: int = 0
    storage_gb: float = 0
    
    def can_allocate(self, available: 'ResourceAllocation') -> bool:
        """Check if resources can be allocated"""
        return (
            self.cpu_cores <= available.cpu_cores and
            self.memory_mb <= available.memory_mb and
            self.gpu_count <= available.gpu_count and
            self.storage_gb <= available.storage_gb
        )

@dataclass
class ProcessingMetrics:
    """Metrics for batch processing"""
    total_projects: int = 0
    completed_projects: int = 0
    failed_projects: int = 0
    average_processing_time: float = 0.0
    resource_utilization: Dict[str, float] = field(default_factory=dict)
    queue_depth: Dict[str, int] = field(default_factory=dict)

# ============================================================================
# BATCH PROCESSING SERVICE
# ============================================================================

class BatchProcessingService:
    """Service for optimized batch video processing"""
    
    def __init__(self):
        self.redis_client = None
        self.resource_monitor = ResourceMonitor()
        self.batch_optimizer = BatchOptimizer()
        self.progress_tracker = BatchProgressTracker()
        
        # Processing configuration
        self.max_parallel_batches = 5
        self.max_projects_per_batch = 50
        self.resource_check_interval = 30  # seconds
        
        # Resource limits per task type
        self.resource_requirements = {
            "content": ResourceAllocation(cpu_cores=1, memory_mb=512),
            "tts": ResourceAllocation(cpu_cores=1, memory_mb=1024),
            "video": ResourceAllocation(cpu_cores=2, memory_mb=2048),
            "advanced_video": ResourceAllocation(cpu_cores=4, memory_mb=4096),
            "ultra_video": ResourceAllocation(cpu_cores=4, memory_mb=8192, gpu_count=1)
        }
    
    # ========================================================================
    # BATCH CREATION AND VALIDATION
    # ========================================================================
    
    async def create_batch(
        self,
        user_id: int,
        project_ids: List[int],
        settings: Dict[str, Any],
        priority: Optional[BatchPriority] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> BatchJob:
        """Create and validate a new batch job"""
        
        # Validate batch size
        if len(project_ids) > self.max_projects_per_batch:
            raise ValueError(f"Batch size exceeds limit of {self.max_projects_per_batch}")
        
        # Validate projects
        valid_project_ids = await self._validate_projects(user_id, project_ids)
        
        if not valid_project_ids:
            raise ValueError("No valid projects found for batch processing")
        
        # Create batch job
        batch_job = BatchJob(
            batch_id=f"batch_{uuid.uuid4()}",
            user_id=user_id,
            project_ids=valid_project_ids,
            settings=settings,
            priority=priority or BatchPriority.NORMAL,
            metadata=metadata or {}
        )
        
        # Store batch job
        await self._store_batch_job(batch_job)
        
        logger.info(f"✅ Created batch job {batch_job.batch_id} with {len(valid_project_ids)} projects")
        
        return batch_job
    
    async def _validate_projects(self, user_id: int, project_ids: List[int]) -> List[int]:
        """Validate projects for batch processing"""
        
        async with AsyncSessionLocal() as db:
            # Get all projects
            result = await db.execute(
                select(Project).where(
                    and_(
                        Project.id.in_(project_ids),
                        Project.user_id == user_id,
                        Project.status.in_([ProjectStatus.DRAFT, ProjectStatus.COMPLETED])
                    )
                )
            )
            projects = result.scalars().all()
            
            valid_ids = []
            
            for project in projects:
                # Check if project has required data
                if project.script and (
                    settings.get("skip_tts") or project.audio_file_path
                ):
                    valid_ids.append(project.id)
            
            return valid_ids
    
    # ========================================================================
    # BATCH EXECUTION
    # ========================================================================
    
    async def execute_batch(self, batch_id: str) -> Dict[str, Any]:
        """Execute a batch job with resource optimization"""
        
        batch_job = await self._get_batch_job(batch_id)
        
        if not batch_job:
            raise ValueError(f"Batch job {batch_id} not found")
        
        try:
            # Update batch status
            batch_job.status = "processing"
            batch_job.started_at = datetime.utcnow()
            await self._update_batch_job(batch_job)
            
            # Initialize progress tracking
            await self.progress_tracker.init_batch(batch_job)
            
            # Optimize batch execution plan
            execution_plan = await self.batch_optimizer.optimize_batch(batch_job)
            
            # Execute with resource management
            results = await self._execute_with_resources(batch_job, execution_plan)
            
            # Update batch completion
            batch_job.status = "completed"
            batch_job.completed_at = datetime.utcnow()
            batch_job.progress = 100.0
            batch_job.results = results
            await self._update_batch_job(batch_job)
            
            logger.info(f"✅ Batch {batch_id} completed successfully")
            
            return results
            
        except Exception as e:
            logger.error(f"💥 Batch execution failed: {e}")
            
            # Update batch status
            batch_job.status = "failed"
            batch_job.results["error"] = str(e)
            await self._update_batch_job(batch_job)
            
            raise
    
    async def _execute_with_resources(
        self,
        batch_job: BatchJob,
        execution_plan: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute batch with resource management"""
        
        results = {
            "successful": [],
            "failed": [],
            "skipped": []
        }
        
        # Group tasks by resource requirements
        task_groups = self._group_tasks_by_resources(execution_plan)
        
        # Process each group with appropriate concurrency
        for group_name, tasks in task_groups.items():
            group_results = await self._process_task_group(
                batch_job,
                group_name,
                tasks
            )
            
            results["successful"].extend(group_results["successful"])
            results["failed"].extend(group_results["failed"])
            results["skipped"].extend(group_results["skipped"])
        
        return results
    
    async def _process_task_group(
        self,
        batch_job: BatchJob,
        group_name: str,
        tasks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process a group of similar tasks"""
        
        results = {
            "successful": [],
            "failed": [],
            "skipped": []
        }
        
        # Determine concurrency based on resources
        concurrency = await self._calculate_concurrency(group_name, len(tasks))
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrency)
        
        async def process_with_semaphore(task):
            async with semaphore:
                return await self._process_single_task(batch_job, task)
        
        # Process tasks concurrently
        task_results = await asyncio.gather(
            *[process_with_semaphore(task) for task in tasks],
            return_exceptions=True
        )
        
        # Categorize results
        for i, result in enumerate(task_results):
            if isinstance(result, Exception):
                results["failed"].append({
                    "task": tasks[i],
                    "error": str(result)
                })
            elif result.get("status") == "success":
                results["successful"].append(result)
            elif result.get("status") == "skipped":
                results["skipped"].append(result)
            else:
                results["failed"].append(result)
        
        return results
    
    async def _process_single_task(
        self,
        batch_job: BatchJob,
        task_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a single task within the batch"""
        
        try:
            # Submit to Celery
            task = submit_priority_task(
                task_name=task_config["task_name"],
                args=task_config["args"],
                kwargs=task_config["kwargs"],
                priority=batch_job.priority.value,
                queue=task_config["queue"]
            )
            
            # Update progress
            await self.progress_tracker.update_task_progress(
                batch_job.batch_id,
                task_config["project_id"],
                "submitted",
                {"task_id": task.id}
            )
            
            # Wait for completion (with timeout)
            result = await self._wait_for_task(task, timeout=task_config.get("timeout", 1800))
            
            # Update progress
            await self.progress_tracker.update_task_progress(
                batch_job.batch_id,
                task_config["project_id"],
                "completed",
                result
            )
            
            return {
                "status": "success",
                "project_id": task_config["project_id"],
                "task_id": task.id,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Task failed for project {task_config['project_id']}: {e}")
            
            await self.progress_tracker.update_task_progress(
                batch_job.batch_id,
                task_config["project_id"],
                "failed",
                {"error": str(e)}
            )
            
            return {
                "status": "failed",
                "project_id": task_config["project_id"],
                "error": str(e)
            }
    
    # ========================================================================
    # RESOURCE MANAGEMENT
    # ========================================================================
    
    async def _calculate_concurrency(
        self,
        task_type: str,
        task_count: int
    ) -> int:
        """Calculate optimal concurrency based on available resources"""
        
        # Get current resource usage
        available = await self.resource_monitor.get_available_resources()
        
        # Get requirements per task
        requirements = self.resource_requirements.get(task_type)
        
        if not requirements:
            return 1
        
        # Calculate max concurrent tasks
        max_by_cpu = available.cpu_cores // requirements.cpu_cores
        max_by_memory = available.memory_mb // requirements.memory_mb
        max_by_gpu = (available.gpu_count // requirements.gpu_count 
                      if requirements.gpu_count > 0 else float('inf'))
        
        # Take minimum and apply limits
        max_concurrent = max(1, min(max_by_cpu, max_by_memory, max_by_gpu))
        
        # Apply batch parallel limit
        max_concurrent = min(max_concurrent, self.batch_optimizer.parallel_limit)
        
        # Don't exceed task count
        max_concurrent = min(max_concurrent, task_count)
        
        logger.info(f"Calculated concurrency for {task_type}: {max_concurrent}")
        
        return max_concurrent
    
    def _group_tasks_by_resources(
        self,
        execution_plan: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group tasks by resource requirements"""
        
        groups = defaultdict(list)
        
        for task in execution_plan:
            task_type = task.get("type", "content")
            groups[task_type].append(task)
        
        return dict(groups)
    
    # ========================================================================
    # BATCH MONITORING
    # ========================================================================
    
    async def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """Get detailed batch status"""
        
        batch_job = await self._get_batch_job(batch_id)
        
        if not batch_job:
            return {"error": "Batch not found"}
        
        # Get progress details
        progress_details = await self.progress_tracker.get_batch_progress(batch_id)
        
        # Get resource metrics
        metrics = await self._get_batch_metrics(batch_job)
        
        return {
            "batch_id": batch_id,
            "status": batch_job.status,
            "progress": batch_job.progress,
            "created_at": batch_job.created_at.isoformat(),
            "started_at": batch_job.started_at.isoformat() if batch_job.started_at else None,
            "completed_at": batch_job.completed_at.isoformat() if batch_job.completed_at else None,
            "total_projects": len(batch_job.project_ids),
            "completed_projects": progress_details["completed"],
            "failed_projects": progress_details["failed"],
            "metrics": metrics,
            "results": batch_job.results
        }
    
    async def list_user_batches(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List user's batch jobs"""
        
        if not self.redis_client:
            self.redis_client = await redis.from_url(settings.REDIS_URL)
        
        # Get batch keys
        pattern = f"batch:user:{user_id}:*"
        keys = await self.redis_client.keys(pattern)
        
        batches = []
        
        for key in keys[-limit:]:  # Get most recent
            batch_data = await self.redis_client.get(key)
            if batch_data:
                batch = json.loads(batch_data)
                
                if not status or batch["status"] == status:
                    batches.append({
                        "batch_id": batch["batch_id"],
                        "status": batch["status"],
                        "progress": batch["progress"],
                        "total_projects": len(batch["project_ids"]),
                        "created_at": batch["created_at"]
                    })
        
        return sorted(batches, key=lambda x: x["created_at"], reverse=True)
    
    # ========================================================================
    # BATCH OPTIMIZATION
    # ========================================================================
    
    async def optimize_batch_settings(
        self,
        project_ids: List[int],
        target_completion_time: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """Optimize batch settings for performance"""
        
        # Analyze projects
        project_analysis = await self._analyze_projects(project_ids)
        
        # Get resource availability
        resources = await self.resource_monitor.get_resource_forecast()
        
        # Calculate optimal settings
        optimal_settings = self.batch_optimizer.calculate_optimal_settings(
            project_analysis,
            resources,
            target_completion_time
        )
        
        return optimal_settings
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    async def _store_batch_job(self, batch_job: BatchJob):
        """Store batch job in Redis"""
        
        if not self.redis_client:
            self.redis_client = await redis.from_url(settings.REDIS_URL)
        
        # Store batch data
        batch_data = {
            "batch_id": batch_job.batch_id,
            "user_id": batch_job.user_id,
            "project_ids": batch_job.project_ids,
            "settings": batch_job.settings,
            "priority": batch_job.priority.value,
            "status": batch_job.status,
            "progress": batch_job.progress,
            "created_at": batch_job.created_at.isoformat(),
            "results": batch_job.results,
            "metadata": batch_job.metadata
        }
        
        # Store with TTL
        await self.redis_client.setex(
            f"batch:{batch_job.batch_id}",
            86400,  # 24 hours
            json.dumps(batch_data)
        )
        
        # Store user reference
        await self.redis_client.setex(
            f"batch:user:{batch_job.user_id}:{batch_job.batch_id}",
            86400,
            batch_job.batch_id
        )
    
    async def _get_batch_job(self, batch_id: str) -> Optional[BatchJob]:
        """Retrieve batch job from Redis"""
        
        if not self.redis_client:
            self.redis_client = await redis.from_url(settings.REDIS_URL)
        
        batch_data = await self.redis_client.get(f"batch:{batch_id}")
        
        if not batch_data:
            return None
        
        data = json.loads(batch_data)
        
        return BatchJob(
            batch_id=data["batch_id"],
            user_id=data["user_id"],
            project_ids=data["project_ids"],
            settings=data["settings"],
            priority=BatchPriority(data["priority"]),
            status=data["status"],
            progress=data["progress"],
            created_at=datetime.fromisoformat(data["created_at"]),
            results=data["results"],
            metadata=data["metadata"]
        )
    
    async def _update_batch_job(self, batch_job: BatchJob):
        """Update batch job in Redis"""
        await self._store_batch_job(batch_job)
    
    async def _wait_for_task(self, task, timeout: int) -> Dict[str, Any]:
        """Wait for Celery task completion"""
        
        start_time = datetime.utcnow()
        
        while True:
            if task.ready():
                if task.successful():
                    return {"status": "success", "result": task.result}
                else:
                    return {"status": "failed", "error": str(task.info)}
            
            # Check timeout
            if (datetime.utcnow() - start_time).total_seconds() > timeout:
                raise TimeoutError(f"Task {task.id} timed out after {timeout} seconds")
            
            await asyncio.sleep(1)
    
    async def _get_batch_metrics(self, batch_job: BatchJob) -> ProcessingMetrics:
        """Get metrics for a batch job"""
        
        metrics = ProcessingMetrics(
            total_projects=len(batch_job.project_ids)
        )
        
        if batch_job.results:
            metrics.completed_projects = len(batch_job.results.get("successful", []))
            metrics.failed_projects = len(batch_job.results.get("failed", []))
        
        if batch_job.started_at and batch_job.completed_at:
            duration = (batch_job.completed_at - batch_job.started_at).total_seconds()
            if metrics.completed_projects > 0:
                metrics.average_processing_time = duration / metrics.completed_projects
        
        return metrics
    
    async def _analyze_projects(self, project_ids: List[int]) -> Dict[str, Any]:
        """Analyze projects for optimization"""
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Project).where(Project.id.in_(project_ids))
            )
            projects = result.scalars().all()
            
            analysis = {
                "total_projects": len(projects),
                "total_duration": sum(p.duration or 60 for p in projects),
                "has_audio": sum(1 for p in projects if p.audio_file_path),
                "has_video": sum(1 for p in projects if p.video_file_path),
                "average_duration": sum(p.duration or 60 for p in projects) / len(projects)
            }
            
            return analysis

# ============================================================================
# RESOURCE MONITOR
# ============================================================================

class ResourceMonitor:
    """Monitor system resources for batch processing"""
    
    def __init__(self):
        self.history_window = 300  # 5 minutes
        self.resource_history = defaultdict(list)
    
    async def get_available_resources(self) -> ResourceAllocation:
        """Get currently available system resources"""
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        available_cpu = max(1, int(cpu_count * (100 - cpu_percent) / 100))
        
        # Memory
        memory = psutil.virtual_memory()
        available_memory_mb = int(memory.available / 1024 / 1024)
        
        # GPU (simplified - would use nvidia-ml-py in production)
        available_gpu = await self._get_available_gpu_count()
        
        # Storage
        disk = psutil.disk_usage('/')
        available_storage_gb = disk.free / 1024 / 1024 / 1024
        
        return ResourceAllocation(
            cpu_cores=available_cpu,
            memory_mb=available_memory_mb,
            gpu_count=available_gpu,
            storage_gb=available_storage_gb
        )
    
    async def get_resource_forecast(self) -> Dict[str, Any]:
        """Forecast resource availability"""
        
        current = await self.get_available_resources()
        
        # Simple forecast based on recent history
        forecast = {
            "current": current,
            "next_5min": current,  # Simplified
            "next_15min": current,
            "trend": "stable"
        }
        
        return forecast
    
    async def _get_available_gpu_count(self) -> int:
        """Get available GPU count"""
        
        # Simplified implementation
        # In production, use nvidia-ml-py or similar
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                utilizations = [float(u) for u in result.stdout.strip().split('\n')]
                # Consider GPU available if < 80% utilized
                return sum(1 for u in utilizations if u < 80)
        except:
            pass
        
        return 0

# ============================================================================
# BATCH OPTIMIZER
# ============================================================================

class BatchOptimizer:
    """Optimize batch execution plans"""
    
    def __init__(self):
        self.parallel_limit = 5
        self.optimization_strategies = {
            "speed": self._optimize_for_speed,
            "cost": self._optimize_for_cost,
            "quality": self._optimize_for_quality,
            "balanced": self._optimize_balanced
        }
    
    async def optimize_batch(self, batch_job: BatchJob) -> List[Dict[str, Any]]:
        """Create optimized execution plan for batch"""
        
        execution_plan = []
        
        # Determine optimization strategy
        strategy = batch_job.metadata.get("optimization_strategy", "balanced")
        optimizer = self.optimization_strategies.get(strategy, self._optimize_balanced)
        
        # Create tasks for each project
        for project_id in batch_job.project_ids:
            tasks = await self._create_project_tasks(project_id, batch_job.settings)
            optimized_tasks = optimizer(tasks, batch_job)
            execution_plan.extend(optimized_tasks)
        
        # Sort by priority and dependencies
        execution_plan = self._sort_execution_plan(execution_plan)
        
        return execution_plan
    
    async def _create_project_tasks(
        self,
        project_id: int,
        settings: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Create tasks for a single project"""
        
        tasks = []
        
        # Determine required tasks based on settings
        if settings.get("generate_content", False):
            tasks.append({
                "project_id": project_id,
                "type": "content",
                "task_name": "generate_content",
                "queue": "content",
                "args": [project_id],
                "kwargs": settings.get("content_settings", {}),
                "priority": 1,
                "timeout": 300
            })
        
        if settings.get("generate_tts", False):
            tasks.append({
                "project_id": project_id,
                "type": "tts",
                "task_name": "generate_tts",
                "queue": "content",
                "args": [project_id],
                "kwargs": settings.get("tts_settings", {}),
                "priority": 2,
                "timeout": 300,
                "depends_on": ["content"] if settings.get("generate_content") else []
            })
        
        # Video generation task
        video_quality = settings.get("video_quality", "medium")
        
        if video_quality == "ultra":
            task_type = "ultra_video"
            queue = "gpu"
            timeout = 3600
        elif settings.get("advanced_video", False):
            task_type = "advanced_video"
            queue = "video"
            timeout = 1800
        else:
            task_type = "video"
            queue = "video"
            timeout = 900
        
        tasks.append({
            "project_id": project_id,
            "type": task_type,
            "task_name": f"generate_{task_type}",
            "queue": queue,
            "args": [project_id],
            "kwargs": settings.get("video_settings", {}),
            "priority": 3,
            "timeout": timeout,
            "depends_on": ["tts"] if settings.get("generate_tts") else []
        })
        
        return tasks
    
    def _optimize_for_speed(
        self,
        tasks: List[Dict[str, Any]],
        batch_job: BatchJob
    ) -> List[Dict[str, Any]]:
        """Optimize for fastest completion"""
        
        # Increase parallelism
        for task in tasks:
            task["priority"] = BatchPriority.HIGH.value
        
        return tasks
    
    def _optimize_for_cost(
        self,
        tasks: List[Dict[str, Any]],
        batch_job: BatchJob
    ) -> List[Dict[str, Any]]:
        """Optimize for lowest cost"""
        
        # Use lower priority queues
        for task in tasks:
            task["priority"] = BatchPriority.LOW.value
            
            # Prefer CPU over GPU when possible
            if task["type"] == "advanced_video" and task.get("queue") == "gpu":
                task["queue"] = "video"
        
        return tasks
    
    def _optimize_for_quality(
        self,
        tasks: List[Dict[str, Any]],
        batch_job: BatchJob
    ) -> List[Dict[str, Any]]:
        """Optimize for highest quality"""
        
        # Use highest quality settings
        for task in tasks:
            if task["type"] in ["video", "advanced_video"]:
                task["kwargs"]["quality"] = "high"
        
        return tasks
    
    def _optimize_balanced(
        self,
        tasks: List[Dict[str, Any]],
        batch_job: BatchJob
    ) -> List[Dict[str, Any]]:
        """Balanced optimization"""
        
        # Default optimization
        return tasks
    
    def _sort_execution_plan(
        self,
        execution_plan: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Sort tasks by priority and dependencies"""
        
        # Simple topological sort based on dependencies
        sorted_plan = []
        completed_types = set()
        
        while len(sorted_plan) < len(execution_plan):
            for task in execution_plan:
                if task in sorted_plan:
                    continue
                
                # Check if dependencies are satisfied
                deps = task.get("depends_on", [])
                if all(dep in completed_types for dep in deps):
                    sorted_plan.append(task)
                    completed_types.add(task["type"])
        
        return sorted_plan
    
    def calculate_optimal_settings(
        self,
        project_analysis: Dict[str, Any],
        resources: Dict[str, Any],
        target_completion_time: Optional[timedelta]
    ) -> Dict[str, Any]:
        """Calculate optimal batch settings"""
        
        settings = {
            "parallel_limit": 3,
            "video_quality": "medium",
            "optimization_strategy": "balanced"
        }
        
        # Adjust based on project count
        if project_analysis["total_projects"] < 10:
            settings["parallel_limit"] = 5
            settings["video_quality"] = "high"
        elif project_analysis["total_projects"] > 30:
            settings["parallel_limit"] = 2
            settings["video_quality"] = "medium"
        
        # Adjust based on target completion time
        if target_completion_time:
            hours = target_completion_time.total_seconds() / 3600
            if hours < 1:
                settings["optimization_strategy"] = "speed"
                settings["parallel_limit"] = 10
            elif hours > 6:
                settings["optimization_strategy"] = "cost"
                settings["parallel_limit"] = 1
        
        return settings

# ============================================================================
# BATCH PROGRESS TRACKER
# ============================================================================

class BatchProgressTracker:
    """Track progress of batch processing"""
    
    def __init__(self):
        self.redis_client = None
    
    async def init_batch(self, batch_job: BatchJob):
        """Initialize progress tracking for batch"""
        
        if not self.redis_client:
            self.redis_client = await redis.from_url(settings.REDIS_URL)
        
        # Initialize progress for each project
        for project_id in batch_job.project_ids:
            await self.redis_client.hset(
                f"batch:progress:{batch_job.batch_id}",
                str(project_id),
                json.dumps({
                    "status": "pending",
                    "started_at": None,
                    "completed_at": None,
                    "tasks": {}
                })
            )
    
    async def update_task_progress(
        self,
        batch_id: str,
        project_id: int,
        status: str,
        details: Dict[str, Any]
    ):
        """Update progress for a specific task"""
        
        if not self.redis_client:
            self.redis_client = await redis.from_url(settings.REDIS_URL)
        
        # Get current progress
        current = await self.redis_client.hget(
            f"batch:progress:{batch_id}",
            str(project_id)
        )
        
        if current:
            progress_data = json.loads(current)
        else:
            progress_data = {"status": "pending", "tasks": {}}
        
        # Update progress
        progress_data["status"] = status
        
        if status == "submitted":
            progress_data["started_at"] = datetime.utcnow().isoformat()
        elif status in ["completed", "failed"]:
            progress_data["completed_at"] = datetime.utcnow().isoformat()
        
        progress_data["tasks"][details.get("task_id", "unknown")] = {
            "status": status,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store updated progress
        await self.redis_client.hset(
            f"batch:progress:{batch_id}",
            str(project_id),
            json.dumps(progress_data)
        )
        
        # Broadcast progress update
        await self._broadcast_progress(batch_id, project_id, progress_data)
    
    async def get_batch_progress(self, batch_id: str) -> Dict[str, Any]:
        """Get overall batch progress"""
        
        if not self.redis_client:
            self.redis_client = await redis.from_url(settings.REDIS_URL)
        
        # Get all project progress
        progress_data = await self.redis_client.hgetall(
            f"batch:progress:{batch_id}"
        )
        
        completed = 0
        failed = 0
        pending = 0
        
        for project_id, data in progress_data.items():
            progress = json.loads(data)
            
            if progress["status"] == "completed":
                completed += 1
            elif progress["status"] == "failed":
                failed += 1
            else:
                pending += 1
        
        total = completed + failed + pending
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "progress_percentage": (completed / total * 100) if total > 0 else 0
        }
    
    async def _broadcast_progress(
        self,
        batch_id: str,
        project_id: int,
        progress_data: Dict[str, Any]
    ):
        """Broadcast progress updates via WebSocket"""
        
        # Get batch job to find user
        batch_data = await self.redis_client.get(f"batch:{batch_id}")
        
        if batch_data:
            batch_info = json.loads(batch_data)
            user_id = batch_info.get("user_id")
            
            if user_id:
                # Broadcast to user
                await manager.broadcast_to_user(
                    str(user_id),
                    {
                        "type": "batch_progress",
                        "batch_id": batch_id,
                        "project_id": project_id,
                        "progress": progress_data
                    }
                )

# ============================================================================
# BATCH RECOVERY
# ============================================================================

class BatchRecoveryService:
    """Handle batch failure recovery"""
    
    def __init__(self):
        self.max_retry_attempts = 3
        self.retry_delay = 300  # 5 minutes
    
    async def recover_failed_batch(
        self,
        batch_id: str,
        retry_failed_only: bool = True
    ) -> Dict[str, Any]:
        """Recover a failed batch by retrying failed tasks"""
        
        # Implementation for batch recovery
        pass
    
    async def auto_recover_batches(self):
        """Automatically recover failed batches (scheduled task)"""
        
        # Implementation for auto recovery
        pass

# Initialize services
batch_processing_service = BatchProcessingService()
batch_recovery_service = BatchRecoveryService()
