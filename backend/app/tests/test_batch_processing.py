# backend/tests/test_batch_processing.py
"""
Test batch processing functionality
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from app.services.batch_processing import (
    batch_processing_service,
    BatchPriority,
    BatchJob
)
from app.tasks.batch_tasks import (
    process_batch_task,
    orchestrate_batch_workflow_task,
    optimize_batch_execution_task
)

@pytest.mark.asyncio
async def test_create_batch():
    """Test batch creation"""
    
    # Create test batch
    batch_job = await batch_processing_service.create_batch(
        user_id=1,
        project_ids=[1, 2, 3, 4, 5],
        settings={
            "video_quality": "medium",
            "parallel_limit": 3
        },
        priority=BatchPriority.NORMAL
    )
    
    assert batch_job.batch_id.startswith("batch_")
    assert len(batch_job.project_ids) == 5
    assert batch_job.priority == BatchPriority.NORMAL

@pytest.mark.asyncio
async def test_batch_optimization():
    """Test batch optimization"""
    
    # Create batch
    batch_job = await batch_processing_service.create_batch(
        user_id=1,
        project_ids=list(range(1, 21)),  # 20 projects
        settings={"video_quality": "high"},
        priority=BatchPriority.LOW
    )
    
    # Optimize settings
    optimal_settings = await batch_processing_service.optimize_batch_settings(
        batch_job.project_ids,
        target_completion_time=timedelta(hours=1)
    )
    
    assert "parallel_limit" in optimal_settings
    assert optimal_settings["parallel_limit"] > 1

@pytest.mark.asyncio
async def test_resource_monitoring():
    """Test resource monitoring"""
    
    # Get available resources
    resources = await batch_processing_service.resource_monitor.get_available_resources()
    
    assert resources.cpu_cores > 0
    assert resources.memory_mb > 0
    
    # Get resource forecast
    forecast = await batch_processing_service.resource_monitor.get_resource_forecast()
    
    assert "current" in forecast
    assert "trend" in forecast

def test_batch_task_submission():
    """Test batch task submission"""
    
    # Submit batch processing task
    result = process_batch_task.delay("test_batch_123")
    
    assert result.id is not None
    assert result.state == "PENDING"

if __name__ == "__main__":
    # Run simple test
    asyncio.run(test_create_batch())
    print("✅ Batch processing tests passed!")
