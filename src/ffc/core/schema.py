"""Schema definitions for the FFC Framework DSL."""

from typing import Any

from pydantic import BaseModel, Field


class ResourceLimits(BaseModel):
    """Resource limits for task execution."""

    memory_mb: int = Field(default=1024, description="Memory limit in MB", gt=0)
    cpu_cores: float = Field(default=1.0, description="CPU cores limit")
    timeout_sec: int = Field(default=300, description="Timeout in seconds", gt=0)


class Permission(BaseModel):
    """Permission definition for tools and resources."""

    resource: str = Field(..., description="Resource identifier")
    actions: list[str] = Field(..., description="Allowed actions")
    conditions: dict[str, Any] | None = Field(
        default=None, description="Conditional requirements"
    )


class RetryPolicy(BaseModel):
    """Retry policy for task execution."""

    max_attempts: int = Field(default=3, description="Maximum retry attempts")
    initial_delay_sec: float = Field(
        default=1.0, description="Initial delay between retries in seconds"
    )
    max_delay_sec: float = Field(
        default=60.0, description="Maximum delay between retries in seconds"
    )
    backoff_factor: float = Field(default=2.0, description="Exponential backoff factor")


class TaskDependency(BaseModel):
    """Task dependency definition."""

    task_id: str = Field(..., description="ID of the dependent task")
    condition: str | None = Field(default=None, description="Condition for dependency")
    timeout_sec: int | None = Field(
        default=None, description="Timeout for waiting on dependency"
    )


class Task(BaseModel):
    """Task definition in the DSL."""

    id: str = Field(..., description="Unique task identifier")
    tool: str = Field(..., description="Tool to execute")
    args: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    description: str | None = Field(default=None, description="Task description")
    resources: ResourceLimits | None = Field(
        default=None, description="Resource limits"
    )
    retry_policy: RetryPolicy | None = Field(default=None, description="Retry policy")
    dependencies: list[TaskDependency] = Field(
        default_factory=list, description="Task dependencies"
    )
    timeout_sec: int | None = Field(default=None, description="Task timeout in seconds")
    critical: bool = Field(
        default=False, description="If True, failure stops execution"
    )


class TelemetryConfig(BaseModel):
    """Telemetry configuration."""

    enabled: bool = Field(default=True, description="Enable telemetry collection")
    log_level: str = Field(default="INFO", description="Logging level")
    metrics: list[str] = Field(default_factory=list, description="Metrics to collect")
    trace_enabled: bool = Field(default=False, description="Enable distributed tracing")


class AgentSpec(BaseModel):
    """Complete agent specification in the DSL."""

    version: str = Field(default="1.0", description="DSL version")
    name: str = Field(..., description="Agent name")
    description: str | None = Field(default=None, description="Agent description")
    permissions: list[Permission] = Field(
        default_factory=list, description="Required permissions"
    )
    tasks: list[Task] = Field(..., description="Tasks to execute")
    resources: ResourceLimits | None = Field(
        default=None, description="Global resource limits"
    )
    telemetry: TelemetryConfig | None = Field(
        default=None, description="Telemetry configuration"
    )
    environment: dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


def validate_dsl(data: dict[str, Any]) -> AgentSpec:
    """Validate DSL data against the schema.

    Args:
        data: DSL data to validate

    Returns:
        Validated AgentSpec instance

    Raises:
        ValueError: If validation fails
    """
    try:
        return AgentSpec(**data)
    except Exception as e:
        raise ValueError(f"DSL validation failed: {e!s}") from e
