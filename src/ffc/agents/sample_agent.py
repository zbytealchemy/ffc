from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

from ..core.base_agent import AgentContext, BaseAgent


class TaskStatus(Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class Task:
    id: str
    func: Callable[..., Awaitable[Any]]
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    dependencies: set[str] = field(default_factory=set)
    max_retries: int = 3
    retry_delay: float = 1.0  # seconds
    schedule_time: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    retry_count: int = 0
    result: Any = None
    error: Optional[Exception] = None

class SampleAgent(BaseAgent):
    """Sample agent implementation demonstrating task management capabilities."""

    def __init__(
        self,
        name: str,
        context: Optional[AgentContext] = None
    ) -> None:
        super().__init__(name, context)
        self.tasks: dict[str, Task] = {}

    async def initialize(self) -> None:
        """Initialize the agent."""
        self.logger.info(f"Initializing agent {self.name}")

    async def run(self) -> None:
        """Run all pending tasks."""
        await self.process_tasks()

    async def cleanup(self) -> None:
        """Clean up any resources."""
        self.logger.info(f"Cleaning up agent {self.name}")
        # Cancel any running tasks if needed
        pass

    async def stop(self) -> None:
        """Stop the agent."""
        self.logger.info(f"Stopping agent {self.name}")
        await self.cleanup()

    async def add_task(
        self,
        task_id: str,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        dependencies: Optional[set[str]] = None,
        schedule_time: Optional[datetime] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs: Any
    ) -> None:
        """Add a task to the agent's task list."""
        if task_id in self.tasks:
            raise ValueError(f"Task with id {task_id} already exists")

        task = Task(
            id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            dependencies=dependencies or set(),
            max_retries=max_retries,
            retry_delay=retry_delay,
            schedule_time=schedule_time
        )
        self.tasks[task_id] = task

    def _can_execute_task(self, task: Task) -> bool:
        """Check if a task can be executed based on its dependencies."""
        if not task.dependencies:
            return True
            
        return all(
            dep_id in self.tasks and self.tasks[dep_id].status == TaskStatus.COMPLETED
            for dep_id in task.dependencies
        )

    async def _execute_task(self, task: Task) -> None:
        """Execute a single task with retry logic."""
        if not self._can_execute_task(task):
            return

        while True:
            try:
                task.status = TaskStatus.RUNNING
                task.result = await task.func(*task.args, **task.kwargs)
                task.status = TaskStatus.COMPLETED
                self.logger.info(f"Task {task.id} completed successfully")
                return
            except Exception as e:
                task.error = e
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.status = TaskStatus.RETRYING
                    self.logger.warning(
                        f"Task {task.id} failed, retrying {task.retry_count}/{task.max_retries}"
                    )
                    await asyncio.sleep(task.retry_delay)
                else:
                    task.status = TaskStatus.FAILED
                    self.logger.error(f"Task {task.id} failed after {task.max_retries} retries")
                    raise

    async def process_tasks(self, max_concurrent: int = 5) -> None:
        """Process all tasks respecting dependencies and concurrency limits."""
        while True:
            eligible_tasks = [
                task for task in self.tasks.values()
                if task.status == TaskStatus.PENDING 
                and self._can_execute_task(task)
                and (not task.schedule_time or datetime.now() >= task.schedule_time)
            ]
            
            if not eligible_tasks:
                active_tasks = [
                    t for t in self.tasks.values() 
                    if t.status in (TaskStatus.RUNNING, TaskStatus.RETRYING)
                ]
                if not active_tasks:
                    failed_tasks = [
                        t for t in self.tasks.values() 
                        if t.status == TaskStatus.FAILED
                    ]
                    if failed_tasks:
                        raise failed_tasks[0].error or Exception(f"Task {failed_tasks[0].id} failed")
                    break
                await asyncio.sleep(0.1)
                continue

            tasks_to_run = eligible_tasks[:max_concurrent]
            try:
                await asyncio.gather(*(self._execute_task(task) for task in tasks_to_run))
            except Exception as e:
                failed_tasks = [
                    t for t in self.tasks.values() 
                    if t.status == TaskStatus.FAILED
                ]
                if failed_tasks:
                    raise failed_tasks[0].error or Exception(f"Task {failed_tasks[0].id} failed") from e
                raise

    def get_status(self) -> str:
        """Get the current status of all tasks."""
        status_counts = {status: 0 for status in TaskStatus}
        for task in self.tasks.values():
            status_counts[task.status] += 1
        
        return (f"{self.name} has {len(self.tasks)} tasks: " + 
                ", ".join(f"{status.value}: {count}" 
                         for status, count in status_counts.items() 
                         if count > 0))
