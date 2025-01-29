"""Task Management System for the FFC Framework.

This module provides a robust task management system with support for:
- Priority-based scheduling
- Parallel execution
- Dependency management
- Retry mechanisms
- Resource-aware execution
"""

from __future__ import annotations

import asyncio
import enum
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Generic, TypeVar

from .resources import ResourceTracker
from .telemetry import TelemetryManager
from .types import AgentState, AgentStatus

logger = logging.getLogger(__name__)

T = TypeVar("T")
TaskFunc = Callable[..., Awaitable[T]]


class TaskStatus(enum.Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING = "waiting"  # Waiting for dependencies


class RetryPolicy:
    """Configurable retry policy with exponential backoff."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ):
        """Initialize retry policy.

        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            backoff_factor: Multiplicative factor for backoff
            jitter: Whether to add random jitter to delays
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for current retry attempt."""
        delay = min(
            self.initial_delay * (self.backoff_factor**attempt), self.max_delay
        )
        if self.jitter:
            # Add ±20% random jitter
            delay *= 0.8 + (time.time() % 0.4)
        return delay


def create_default_agent_state() -> AgentState:
    """Create a default agent state.

    Returns:
        Default agent state with empty memory and context
    """
    return AgentState(
        memory={},
        context={},
        state=AgentStatus.INITIALIZED,
        working_dir=None,
        permissions=None,
        resources=None,
        telemetry=None
    )


@dataclass
class Task(Generic[T]):
    """Represents a task in the system."""

    id: str
    func: TaskFunc[T]
    args: tuple = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    dependencies: set[str] = field(default_factory=set)
    retry_policy: RetryPolicy | None = None
    state: AgentState = field(default_factory=create_default_agent_state)

    # Runtime fields
    status: TaskStatus = field(default=TaskStatus.PENDING)
    result: T | None = None
    error: Exception | None = None
    retry_count: int = field(default=0)
    scheduled_time: datetime | None = None
    started_time: datetime | None = None
    completed_time: datetime | None = None

    def __post_init__(self):
        if self.scheduled_time is None:
            self.scheduled_time = datetime.now()

    @property
    def duration(self) -> timedelta | None:
        """Return task duration if completed."""
        if self.completed_time and self.started_time:
            return self.completed_time - self.started_time
        return None

    def __lt__(self, other: Task) -> bool:
        """Compare tasks by priority for priority queue."""
        if not isinstance(other, Task):
            return NotImplemented
        return self.priority < other.priority


class TaskScheduler:
    """Manages task scheduling and execution."""

    def __init__(
        self,
        max_workers: int = 10,
        resource_tracker: ResourceTracker | None = None,
        telemetry: TelemetryManager | None = None,
    ):
        """Initialize scheduler.

        Args:
            max_workers: Maximum number of concurrent tasks
            resource_tracker: Optional resource tracker for monitoring
            telemetry: Optional telemetry manager for metrics
        """
        self.max_workers = max_workers
        self.resource_tracker = resource_tracker
        self.telemetry = telemetry

        self._tasks: dict[str, Task] = {}
        self._running: set[str] = set()
        self._completed: set[str] = set()
        self._failed: set[str] = set()
        self._workers: list[asyncio.Task] = []
        self._stop_event = asyncio.Event()
        self._pending: asyncio.PriorityQueue | None = None
        self._waiting_tasks: dict[str, set[str]] = {}  # task_id -> dependent task IDs

    async def submit(self, task: Task) -> None:
        """Submit a task for execution."""
        loop = asyncio.get_running_loop()
        logger.debug(f"Submitting task {task.id} in loop {id(loop)}")
        
        self._tasks[task.id] = task

        # Handle dependencies
        if task.dependencies:
            unsatisfied = {
                dep_id for dep_id in task.dependencies if dep_id not in self._completed
            }
            if unsatisfied:
                task.status = TaskStatus.WAITING
                # Register this task as waiting on its dependencies
                for dep_id in unsatisfied:
                    if dep_id not in self._waiting_tasks:
                        self._waiting_tasks[dep_id] = set()
                    self._waiting_tasks[dep_id].add(task.id)
                return

        # Add to pending queue with negated priority (higher priority = lower number)
        if self._pending is None:
            raise RuntimeError("Scheduler not started")
            
        logger.debug(f"Adding task {task.id} to queue in loop {id(loop)}")
        await self._pending.put((-task.priority, task))

        if self.telemetry:
            self.telemetry.record_metric(
                "task_submitted", {"task_id": task.id, "priority": task.priority}
            )

    async def _execute_task(self, task: Task) -> None:
        """Execute a single task with retry logic."""
        task.started_time = datetime.now()
        task.status = TaskStatus.RUNNING
        self._running.add(task.id)

        try:
            if self.resource_tracker:
                async with self.resource_tracker.track_resources():
                    task.result = await task.func(*task.args, **task.kwargs)
            else:
                task.result = await task.func(*task.args, **task.kwargs)

            task.status = TaskStatus.COMPLETED
            task.completed_time = datetime.now()
            self._completed.add(task.id)
            self._running.remove(task.id)

            # Check for dependent tasks
            await self._check_dependent_tasks(task)

        except Exception as e:
            if task.retry_policy and task.retry_count < task.retry_policy.max_retries:
                delay = task.retry_policy.get_delay(task.retry_count)
                task.retry_count += 1

                logger.warning(
                    f"Task {task.id} failed, retrying in {delay:.2f}s "
                    f"(attempt {task.retry_count}/{task.retry_policy.max_retries})"
                )

                await asyncio.sleep(delay)
                await self._pending.put((-task.priority, task))
            else:
                task.status = TaskStatus.FAILED
                task.error = e
                self._failed.add(task.id)
                self._running.remove(task.id)

                if self.telemetry:
                    self.telemetry.record_metric(
                        "task_failed",
                        {
                            "task_id": task.id,
                            "error": str(e),
                            "retries": task.retry_count,
                        },
                    )

        finally:
            task.completed_time = datetime.now()

    async def _check_dependent_tasks(self, completed_task: Task) -> None:
        """Check and schedule tasks that depend on the completed task."""
        
        waiting_tasks = self._waiting_tasks.pop(completed_task.id, set())
        
        for task_id in waiting_tasks:
            task = self._tasks[task_id]
            # Check if all dependencies are now satisfied
            if all(dep_id in self._completed for dep_id in task.dependencies):
                task.status = TaskStatus.PENDING
                await self._pending.put((-task.priority, task))

    async def _worker(self) -> None:
        """Task worker coroutine."""
        loop = asyncio.get_running_loop()
        logger.debug(f"Worker running in loop {id(loop)}")
        
        while not self._stop_event.is_set():
            try:
                if self._pending is None:
                    logger.error("Queue not initialized")
                    break
                    
                logger.debug(f"Worker waiting for task in loop {id(loop)}")
                _, task = await self._pending.get()
                logger.debug(f"Worker got task {task.id} in loop {id(loop)}")
                await self._execute_task(task)
                self._pending.task_done()
            except asyncio.CancelledError:
                logger.debug("Worker cancelled")
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")

    async def start(self) -> None:
        """Start the task scheduler."""
        loop = asyncio.get_running_loop()
        logger.debug(f"Starting scheduler in loop {id(loop)}")
        
        if not self._pending:
            self._pending = asyncio.PriorityQueue()
            logger.debug(f"Created queue in loop {id(loop)}")
        
        self._workers = []
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(), name=f"worker-{i}")
            self._workers.append(worker)
            logger.debug(f"Created worker {i} in loop {id(loop)}")

    async def stop(self) -> None:
        """Stop the task scheduler."""
        self._stop_event.set()
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)

    def get_task(self, task_id: str) -> Task | None:
        """Get task by ID."""
        return self._tasks.get(task_id)

    @property
    def stats(self) -> dict[str, int]:
        """Return current scheduler statistics."""
        return {
            "pending": self._pending.qsize() if self._pending else 0,
            "running": len(self._running),
            "completed": len(self._completed),
            "failed": len(self._failed),
            "total": len(self._tasks),
        }
