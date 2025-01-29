"""Tests for the Task Management System."""

import asyncio
import logging
import time
from datetime import timedelta

import pytest
from ffc.core.tasks import RetryPolicy, Task, TaskScheduler, TaskStatus

logger = logging.getLogger(__name__)

async def sample_task(x: int, y: int) -> int:
    """Sample task that adds two numbers."""
    await asyncio.sleep(0.1)  # Simulate work
    return x + y


async def failing_task() -> None:
    """Task that always fails."""
    raise ValueError("Task failed")


@pytest.mark.asyncio
async def test_task_execution():
    """Test basic task execution."""
    loop = asyncio.get_running_loop()
    logger.debug(f"Test running in loop {id(loop)}")
    
    scheduler = TaskScheduler(max_workers=2)
    await scheduler.start()

    task = Task(id="task1", func=sample_task, args=(2, 3), priority=1)
    await scheduler.submit(task)
    
    timeout = 5  # seconds
    start_time = time.time()
    while task.status != TaskStatus.COMPLETED:
        if time.time() - start_time > timeout:
            logger.error("Test timed out waiting for task completion")
            break
        logger.debug(f"Waiting for task completion, current status: {task.status}")
        await asyncio.sleep(0.1)

    assert task.status == TaskStatus.COMPLETED, f"Task failed with status {task.status}"
    assert task.result == 5
    assert isinstance(task.duration, timedelta)
    assert task.error is None

    await scheduler.stop()


@pytest.mark.asyncio
async def test_task_dependencies():
    """Test task dependency management."""
    scheduler = TaskScheduler(max_workers=2)
    await scheduler.start()

    task1 = Task(id="task1", func=sample_task, args=(2, 3))
    task2 = Task(id="task2", func=sample_task, args=(4, 5), dependencies={"task1"})

    await scheduler.submit(task2)
    await scheduler.submit(task1)
    
    while task2.status != TaskStatus.COMPLETED:
        await asyncio.sleep(0.1)

    assert task1.status == TaskStatus.COMPLETED
    assert task2.status == TaskStatus.COMPLETED
    assert task1.result == 5
    assert task2.result == 9

    # Verify execution order
    assert task1.completed_time < task2.started_time

    await scheduler.stop()


@pytest.mark.asyncio
async def test_retry_policy():
    """Test retry mechanism."""
    retry_policy = RetryPolicy(
        max_retries=2, initial_delay=0.1, max_delay=1.0, backoff_factor=2.0
    )

    scheduler = TaskScheduler(max_workers=1)
    await scheduler.start()

    task = Task(id="failing_task", func=failing_task, retry_policy=retry_policy)

    await scheduler.submit(task)
    
    while task.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        await asyncio.sleep(0.1)

    assert task.status == TaskStatus.FAILED
    assert task.retry_count == 2
    assert isinstance(task.error, ValueError)
    assert str(task.error) == "Task failed"

    await scheduler.stop()


@pytest.mark.asyncio
async def test_priority_scheduling():
    """Test priority-based task scheduling."""

    scheduler = TaskScheduler(max_workers=1)
    await scheduler.start()

    results = []

    async def priority_task(priority: int) -> None:
        results.append(priority)
        await asyncio.sleep(0.1)

    tasks = [
        Task(id=f"task{i}", func=priority_task, args=(i,), priority=i)
        for i in range(3)
    ]

    for task in reversed(tasks):
        await scheduler.submit(task)

    while not all(task.status == TaskStatus.COMPLETED for task in tasks):
        await asyncio.sleep(0.1)

    assert results == [2, 1, 0]

    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_stats():
    """Test scheduler statistics."""
    scheduler = TaskScheduler(max_workers=2)
    await scheduler.start()

    tasks = [
        Task(id=f"task{i}", func=sample_task, args=(i, i))
        for i in range(3)
    ]
    
    for task in tasks:
        await scheduler.submit(task)

    while not all(task.status == TaskStatus.COMPLETED for task in tasks):
        await asyncio.sleep(0.1)

    stats = scheduler.stats
    assert stats["completed"] == 3
    assert stats["failed"] == 0
    assert stats["total"] == 3

    await scheduler.stop()
