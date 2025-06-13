# backend/app/tasks/monitoring.py
"""
📊 REELS GENERATOR - Monitoring and Management Tasks
Celery tasks for system monitoring and task management
"""

from celery import shared_task
from typing import Dict, Any, List
import logging
import redis
import json
from datetime import datetime, timedelta
from collections import defaultdict

from ..config import settings
from ..database import AsyncSessionLocal
from ..models import Project, User, ProjectStatus
from sqlalchemy import select, func
from .celery_app import celery_app, task_monitor

logger = logging.getLogger(__name__)

# ============================================================================
# MONITORING TASKS
# ============================================================================

@shared_task(name="check_failed_tasks")
def check_failed_tasks() -> Dict[str, Any]:
    """
    Check for failed tasks and send alerts
    
    Scheduled to run every 5 minutes
    """
    
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        
        # Get recent failures
        failures = []
        failure_data = redis_client.lrange("celery:failures", 0, 50)
        
        for item in failure_data:
            try:
                failure = json.loads(item)
                failures.append(failure)
            except:
                continue
        
        # Group failures by task type
        failures_by_task = defaultdict(list)
        for failure in failures:
            failures_by_task[failure.get("task_name", "unknown")].append(failure)
        
        # Check failure thresholds
        alerts = []
        for task_name, task_failures in failures_by_task.items():
            if len(task_failures) >= 5:  # Alert if 5+ failures
                alerts.append({
                    "task": task_name,
                    "count": len(task_failures),
                    "recent_error": task_failures[0].get("error", "Unknown error")
                })
        
        # In production, send alerts via email/Slack
        if alerts:
            logger.warning(f"High failure rate detected: {alerts}")
        
        return {
            "total_failures": len(failures),
            "failures_by_task": {k: len(v) for k, v in failures_by_task.items()},
            "alerts": alerts
        }
        
    except Exception as e:
        logger.error(f"Failed task monitoring error: {e}")
        raise

@shared_task(name="update_usage_statistics")
def update_usage_statistics() -> Dict[str, Any]:
    """
    Update system usage statistics
    
    Scheduled to run every 10 minutes
    """
    
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        
        # Get queue statistics
        queue_stats = task_monitor.get_queue_stats()
        
        # Get worker statistics
        worker_stats = task_monitor.get_worker_stats()
        
        # Calculate task execution metrics
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "queues": queue_stats,
            "workers": worker_stats,
            "task_rates": calculate_task_rates(redis_client),
            "performance": calculate_performance_metrics(redis_client)
        }
        
        # Store metrics
        redis_client.setex(
            "celery:metrics:latest",
            3600,  # 1 hour TTL
            json.dumps(metrics)
        )
        
        # Store historical data
        redis_client.lpush("celery:metrics:history", json.dumps(metrics))
        redis_client.ltrim("celery:metrics:history", 0, 288)  # Keep 2 days of data
        
        logger.info(f"Usage statistics updated: {metrics}")
        
        return metrics
        
    except Exception as e:
        logger.error(f"Usage statistics update failed: {e}")
        raise

@shared_task(name="monitor_task_performance")
def monitor_task_performance() -> Dict[str, Any]:
    """
    Monitor task execution performance
    
    Analyzes execution times and identifies slow tasks
    """
    
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        
        performance_report = {}
        
        # Get all task types
        task_types = [
            "generate_content",
            "generate_tts", 
            "generate_video",
            "generate_advanced_video"
        ]
        
        for task_type in task_types:
            # Get execution times
            execution_times = redis_client.lrange(
                f"celery:stats:execution_times:{task_type}",
                0, -1
            )
            
            if execution_times:
                times = [float(t) for t in execution_times]
                
                performance_report[task_type] = {
                    "avg_execution_time": sum(times) / len(times),
                    "min_execution_time": min(times),
                    "max_execution_time": max(times),
                    "samples": len(times),
                    "slow_tasks": len([t for t in times if t > 300])  # > 5 minutes
                }
        
        # Identify problematic tasks
        alerts = []
        for task_type, stats in performance_report.items():
            if stats.get("avg_execution_time", 0) > 600:  # > 10 minutes average
                alerts.append({
                    "task": task_type,
                    "issue": "high_average_execution_time",
                    "value": stats["avg_execution_time"]
                })
        
        return {
            "performance_report": performance_report,
            "alerts": alerts,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Task performance monitoring failed: {e}")
        raise

# ============================================================================
# CLEANUP AND MAINTENANCE TASKS
# ============================================================================

@shared_task(name="cleanup_stuck_tasks")
def cleanup_stuck_tasks() -> Dict[str, Any]:
    """
    Clean up tasks stuck in processing state
    
    Scheduled to run every hour
    """
    
    try:
        import asyncio
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            stuck_projects = loop.run_until_complete(
                find_stuck_projects()
            )
            
            cleaned = 0
            
            for project in stuck_projects:
                # Check if task is actually running
                if project.get("task_id"):
                    result = celery_app.AsyncResult(project["task_id"])
                    
                    if result.state in ["PENDING", "FAILURE"]:
                        # Mark project as failed
                        loop.run_until_complete(
