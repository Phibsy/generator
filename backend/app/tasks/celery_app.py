# backend/app/tasks/celery_app.py
"""
⚡ REELS GENERATOR - Celery Task System
Week 6: Distributed task queue for scalable video processing
"""

from celery import Celery, Task
from celery.signals import task_prerun, task_postrun, task_failure, worker_ready
from kombu import Exchange, Queue
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional
import redis
import json

from ..config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# CELERY CONFIGURATION
# ============================================================================

# Create Celery app
celery_app = Celery(
    "reels_generator",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.content_tasks",
        "app.tasks.video_tasks", 
        "app.tasks.social_media_tasks"
    ]
)

# ============================================================================
# CELERY SETTINGS
# ============================================================================

celery_app.conf.update(
    # Task execution settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={
        'master_name': 'mymaster',
        'visibility_timeout': 3600,
    },
    
    # Task routing
    task_routes={
        'app.tasks.content_tasks.*': {'queue': 'content'},
        'app.tasks.video_tasks.*': {'queue': 'video', 'priority': 5},
        'app.tasks.video_tasks.process_ultra_quality_video': {'queue': 'gpu', 'priority': 10},
        'app.tasks.social_media_tasks.*': {'queue': 'social'},
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Disable prefetching for fair distribution
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks to prevent memory leaks
    worker_disable_rate_limits=False,
    
    # Task execution limits
    task_soft_time_limit=1800,  # 30 minutes soft limit
    task_time_limit=3600,  # 1 hour hard limit
    task_acks_late=True,  # Tasks acknowledged after completion
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Priority settings
    task_inherit_parent_priority=True,
    task_default_priority=5,
    task_queue_max_priority=10,
    
    # Beat scheduler (for periodic tasks)
    beat_schedule={
        'cleanup-temp-files': {
            'task': 'app.tasks.video_tasks.cleanup_temp_files',
            'schedule': 3600.0,  # Every hour
        },
        'check-failed-tasks': {
            'task': 'app.tasks.monitoring.check_failed_tasks',
            'schedule': 300.0,  # Every 5 minutes
        },
        'update-usage-stats': {
            'task': 'app.tasks.monitoring.update_usage_statistics',
            'schedule': 600.0,  # Every 10 minutes
        },
    },
    
    # Error handling
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
)

# ============================================================================
# QUEUE CONFIGURATION
# ============================================================================

# Define exchanges
default_exchange = Exchange('reels', type='direct')
priority_exchange = Exchange('priority', type='topic')

# Define queues with different priorities
celery_app.conf.task_queues = (
    # Content generation queue (AI tasks)
    Queue(
        'content',
        exchange=default_exchange,
        routing_key='content',
        queue_arguments={
            'x-max-priority': 5,
            'x-message-ttl': 3600000,  # 1 hour TTL
        }
    ),
    
    # Video processing queue (CPU intensive)
    Queue(
        'video',
        exchange=default_exchange,
        routing_key='video',
        queue_arguments={
            'x-max-priority': 10,
            'x-message-ttl': 7200000,  # 2 hours TTL
        }
    ),
    
    # GPU processing queue (for high-quality rendering)
    Queue(
        'gpu',
        exchange=priority_exchange,
        routing_key='gpu.*',
        queue_arguments={
            'x-max-priority': 10,
            'x-message-ttl': 3600000,
        }
    ),
    
    # Social media publishing queue
    Queue(
        'social',
        exchange=default_exchange,
        routing_key='social',
        queue_arguments={
            'x-max-priority': 3,
        }
    ),
    
    # Default queue for misc tasks
    Queue(
        'celery',
        exchange=default_exchange,
        routing_key='celery',
    ),
)

# ============================================================================
# CUSTOM TASK BASE CLASS
# ============================================================================

class ReelsTask(Task):
    """Base task class with progress tracking and error handling"""
    
    def __init__(self):
        super().__init__()
        self.redis_client = None
    
    def get_redis_client(self):
        """Get Redis client for progress tracking"""
        if not self.redis_client:
            self.redis_client = redis.from_url(settings.REDIS_URL)
        return self.redis_client
    
    def update_progress(self, task_id: str, progress: float, status: str, details: Dict[str, Any] = None):
        """Update task progress in Redis"""
        redis_client = self.get_redis_client()
        
        progress_data = {
            "task_id": task_id,
            "progress": progress,
            "status": status,
            "details": details or {},
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Store progress
        redis_client.setex(
            f"celery:progress:{task_id}",
            300,  # 5 minutes TTL
            json.dumps(progress_data)
        )
        
        # Publish to channel for real-time updates
        redis_client.publish(
            f"celery:progress:{task_id}",
            json.dumps(progress_data)
        )
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f"Task {task_id} failed: {exc}")
        
        # Update progress with error
        self.update_progress(
            task_id,
            -1,
            "failed",
            {"error": str(exc), "traceback": str(einfo)}
        )
        
        # Store failure info for monitoring
        redis_client = self.get_redis_client()
        failure_data = {
            "task_id": task_id,
            "task_name": self.name,
            "error": str(exc),
            "args": args,
            "kwargs": kwargs,
            "failed_at": datetime.utcnow().isoformat()
        }
        
        redis_client.lpush("celery:failures", json.dumps(failure_data))
        redis_client.ltrim("celery:failures", 0, 999)  # Keep last 1000 failures
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry"""
        logger.warning(f"Task {task_id} retrying: {exc}")
        
        self.update_progress(
            task_id,
            -1,
            "retrying",
            {"error": str(exc), "retry_count": self.request.retries}
        )
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(f"Task {task_id} completed successfully")
        
        # Store completion metrics
        redis_client = self.get_redis_client()
        redis_client.hincrby("celery:stats:completed", self.name, 1)

# Set as default task class
celery_app.Task = ReelsTask

# ============================================================================
# SIGNAL HANDLERS
# ============================================================================

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kw):
    """Before task execution"""
    logger.info(f"Starting task {task.name} with id {task_id}")
    
    # Store task start time
    redis_client = redis.from_url(settings.REDIS_URL)
    redis_client.hset(f"celery:task:{task_id}", "started_at", time.time())
    redis_client.hset(f"celery:task:{task_id}", "status", "running")
    
    # Update active tasks counter
    redis_client.hincrby("celery:stats:active", task.name, 1)

@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kw):
    """After task execution"""
    redis_client = redis.from_url(settings.REDIS_URL)
    
    # Calculate execution time
    start_time = redis_client.hget(f"celery:task:{task_id}", "started_at")
    if start_time:
        execution_time = time.time() - float(start_time)
        logger.info(f"Task {task.name} completed in {execution_time:.2f}s")
        
        # Store execution metrics
        redis_client.hset(f"celery:task:{task_id}", "execution_time", execution_time)
        redis_client.hset(f"celery:task:{task_id}", "completed_at", time.time())
        redis_client.hset(f"celery:task:{task_id}", "state", state)
        
        # Update task execution stats
        redis_client.lpush(f"celery:stats:execution_times:{task.name}", execution_time)
        redis_client.ltrim(f"celery:stats:execution_times:{task.name}", 0, 99)  # Keep last 100
    
    # Update active tasks counter
    redis_client.hincrby("celery:stats:active", task.name, -1)

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **kw):
    """On task failure"""
    logger.error(f"Task {sender.name} failed: {exception}")
    
    redis_client = redis.from_url(settings.REDIS_URL)
    redis_client.hincrby("celery:stats:failed", sender.name, 1)

@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """When worker is ready"""
    logger.info(f"Celery worker ready: {sender}")

# ============================================================================
# TASK MONITORING
# ============================================================================

class TaskMonitor:
    """Monitor task execution and performance"""
    
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL)
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get current task status"""
        # Check Celery result
        result = celery_app.AsyncResult(task_id)
        
        # Get progress from Redis
        progress_data = self.redis_client.get(f"celery:progress:{task_id}")
        progress = json.loads(progress_data) if progress_data else {}
        
        # Get task metadata
        task_data = self.redis_client.hgetall(f"celery:task:{task_id}")
        
        return {
            "task_id": task_id,
            "state": result.state,
            "progress": progress.get("progress", 0),
            "status": progress.get("status", result.state),
            "result": result.result if result.successful() else None,
            "error": str(result.info) if result.failed() else None,
            "started_at": task_data.get(b"started_at", b"").decode(),
            "completed_at": task_data.get(b"completed_at", b"").decode(),
            "execution_time": task_data.get(b"execution_time", b"").decode()
        }
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        stats = {}
        
        for queue_name in ['content', 'video', 'gpu', 'social', 'celery']:
            queue_key = f"celery:queue:{queue_name}"
            stats[queue_name] = {
                "pending": self.redis_client.llen(queue_key),
                "active": int(self.redis_client.hget("celery:stats:active", queue_name) or 0),
                "completed": int(self.redis_client.hget("celery:stats:completed", queue_name) or 0),
                "failed": int(self.redis_client.hget("celery:stats:failed", queue_name) or 0)
            }
        
        return stats
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics"""
        # Get active workers
        inspect = celery_app.control.inspect()
        
        return {
            "active_workers": len(inspect.active() or {}),
            "registered_tasks": list(inspect.registered() or {}).values(),
            "scheduled_tasks": inspect.scheduled(),
            "reserved_tasks": inspect.reserved()
        }

# Initialize monitor
task_monitor = TaskMonitor()

# ============================================================================
# PRIORITY QUEUE HELPERS
# ============================================================================

def submit_priority_task(task_name: str, args: tuple, kwargs: dict, priority: int = 5, queue: str = None):
    """Submit task with priority"""
    
    # Ensure priority is in valid range
    priority = max(0, min(10, priority))
    
    # Determine queue based on task type if not specified
    if not queue:
        if 'content' in task_name:
            queue = 'content'
        elif 'video' in task_name:
            queue = 'gpu' if 'ultra' in str(kwargs) else 'video'
        elif 'social' in task_name:
            queue = 'social'
        else:
            queue = 'celery'
    
    # Submit task with priority
    task = celery_app.send_task(
        task_name,
        args=args,
        kwargs=kwargs,
        queue=queue,
        priority=priority,
        countdown=0
    )
    
    logger.info(f"Submitted task {task.id} to queue {queue} with priority {priority}")
    return task

# ============================================================================
# BATCH PROCESSING
# ============================================================================

def create_batch_job(tasks: list) -> str:
    """Create a batch job for multiple tasks"""
    
    from celery import group
    
    # Create group of tasks
    job = group(tasks)
    
    # Execute group
    result = job.apply_async()
    
    # Store batch info
    batch_id = f"batch_{result.id}"
    redis_client = redis.from_url(settings.REDIS_URL)
    
    batch_info = {
        "batch_id": batch_id,
        "task_ids": [r.id for r in result.results],
        "total_tasks": len(tasks),
        "created_at": datetime.utcnow().isoformat()
    }
    
    redis_client.setex(
        f"celery:batch:{batch_id}",
        3600,  # 1 hour TTL
        json.dumps(batch_info)
    )
    
    return batch_id

def get_batch_status(batch_id: str) -> Dict[str, Any]:
    """Get status of a batch job"""
    
    redis_client = redis.from_url(settings.REDIS_URL)
    batch_data = redis_client.get(f"celery:batch:{batch_id}")
    
    if not batch_data:
        return {"error": "Batch not found"}
    
    batch_info = json.loads(batch_data)
    task_statuses = []
    
    for task_id in batch_info["task_ids"]:
        task_statuses.append(task_monitor.get_task_status(task_id))
    
    completed = sum(1 for t in task_statuses if t["state"] == "SUCCESS")
    failed = sum(1 for t in task_statuses if t["state"] == "FAILURE")
    pending = sum(1 for t in task_statuses if t["state"] == "PENDING")
    
    return {
        "batch_id": batch_id,
        "total_tasks": batch_info["total_tasks"],
        "completed": completed,
        "failed": failed,
        "pending": pending,
        "progress": (completed / batch_info["total_tasks"]) * 100,
        "tasks": task_statuses
    }
