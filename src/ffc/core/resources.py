"""Resource management components for the FFC Framework."""

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import psutil

from .schema import ResourceLimits


@dataclass
class ResourceError(Exception):
    """Base class for resource-related errors."""

    message: str
    resource: str | None = None

    def __str__(self) -> str:
        if self.resource:
            return f"Resource error for '{self.resource}': {self.message}"
        return f"Resource error: {self.message}"


class ResourceTracker:
    """Tracks and enforces resource usage limits."""

    def __init__(self, limits: ResourceLimits | None = None) -> None:
        """Initialize resource tracker.

        Args:
            limits: Resource limits to enforce
        """
        self.limits = limits or ResourceLimits()
        self._usage: dict[str, float] = {
            "memory_mb": 0.0,
            "cpu_cores": 0.0,
            "execution_time": 0.0,
        }
        self._start_time: float | None = None

    async def _check_memory_usage(self) -> None:
        """Check current memory usage against limits.

        Raises:
            ResourceError: If memory limit is exceeded
        """
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)  # Convert to MB
        self._usage["memory_mb"] = memory_mb

        if memory_mb > self.limits.memory_mb:
            raise ResourceError(
                f"Memory limit exceeded: {memory_mb:.1f}MB > {self.limits.memory_mb}MB",
                "memory",
            )

    async def _check_cpu_usage(self) -> None:
        """Check current CPU usage against limits.

        Raises:
            ResourceError: If CPU limit is exceeded
        """
        process = psutil.Process()
        cpu_percent = process.cpu_percent() / 100.0  # Convert to cores
        self._usage["cpu_cores"] = cpu_percent

        if cpu_percent > self.limits.cpu_cores:
            raise ResourceError(
                f"CPU limit exceeded: {cpu_percent:.1f} cores > "
                f"{self.limits.cpu_cores} cores",
                "cpu",
            )

    async def _check_timeout(self) -> None:
        """Check if execution time exceeds timeout.

        Raises:
            ResourceError: If timeout is exceeded
        """
        if not self._start_time:
            return

        execution_time = time.time() - self._start_time
        self._usage["execution_time"] = execution_time

        if execution_time > self.limits.timeout_sec:
            raise ResourceError(
                f"Timeout exceeded: {execution_time:.1f}s > {self.limits.timeout_sec}s",
                "timeout",
            )

    @asynccontextmanager
    async def track_resources(self) -> AsyncGenerator[None, None]:
        """Create a context for tracking resource usage.

        Yields:
            None

        Raises:
            ResourceError: If any resource limit is exceeded
        """
        try:
            self._start_time = time.time()
            await self._check_memory_usage()
            await self._check_cpu_usage()
            yield
        finally:
            if self._start_time:
                await self._check_timeout()
                self._start_time = None

    def get_usage(self) -> dict[str, float]:
        """Get current resource usage statistics.

        Returns:
            Dictionary with current usage values
        """
        return self._usage.copy()
