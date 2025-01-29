"""Tests for DSL schema validation."""

import pytest
from ffc.core.schema import (
    AgentSpec,
    Permission,
    ResourceLimits,
    RetryPolicy,
    Task,
    TaskDependency,
    TelemetryConfig,
    validate_dsl,
)
from pydantic import ValidationError


def test_resource_limits_validation():
    """Test resource limits validation."""
    # Test valid resource limits
    limits = ResourceLimits(memory_mb=2048, cpu_cores=2.0, timeout_sec=600)
    assert limits.memory_mb == 2048
    assert limits.cpu_cores == 2.0
    assert limits.timeout_sec == 600

    # Test default values
    limits = ResourceLimits()
    assert limits.memory_mb == 1024
    assert limits.cpu_cores == 1.0
    assert limits.timeout_sec == 300

    # Test invalid values
    with pytest.raises(ValidationError):
        ResourceLimits(memory_mb=-1)
    with pytest.raises(ValidationError):
        ResourceLimits(memory_mb=0)
    with pytest.raises(ValidationError):
        ResourceLimits(timeout_sec=0)


def test_permission_validation():
    """Test permission validation."""
    # Test valid permission
    perm = Permission(
        resource="file_system",
        actions=["read", "write"],
        conditions={"path": "/data"},
    )
    assert perm.resource == "file_system"
    assert perm.actions == ["read", "write"]
    assert perm.conditions == {"path": "/data"}

    # Test required fields
    with pytest.raises(ValidationError):
        Permission(actions=["read"])
    with pytest.raises(ValidationError):
        Permission(resource="file_system")


def test_task_validation():
    """Test task validation."""
    # Test minimal task
    task = Task(id="task1", tool="copy_file")
    assert task.id == "task1"
    assert task.tool == "copy_file"
    assert task.args == {}
    assert task.critical is False

    # Test full task
    task = Task(
        id="task2",
        tool="process_data",
        args={"input": "data.csv", "output": "result.csv"},
        description="Process CSV data",
        resources=ResourceLimits(memory_mb=4096),
        retry_policy=RetryPolicy(max_attempts=5),
        dependencies=[TaskDependency(task_id="task1")],
        timeout_sec=1800,
        critical=True,
    )
    assert task.id == "task2"
    assert task.description == "Process CSV data"
    assert task.resources.memory_mb == 4096
    assert task.retry_policy.max_attempts == 5
    assert len(task.dependencies) == 1
    assert task.critical is True

    # Test invalid task
    with pytest.raises(ValidationError):
        Task(tool="copy_file")  # Missing id
    with pytest.raises(ValidationError):
        Task(id="task1")  # Missing tool


def test_agent_spec_validation():
    """Test agent specification validation."""
    # Test minimal agent spec
    spec = AgentSpec(
        name="test_agent",
        tasks=[Task(id="task1", tool="echo", args={"message": "hello"})],
    )
    assert spec.name == "test_agent"
    assert len(spec.tasks) == 1
    assert spec.version == "1.0"

    # Test full agent spec
    spec = AgentSpec(
        version="1.1",
        name="data_processor",
        description="Process data files",
        permissions=[
            Permission(resource="file_system", actions=["read", "write"]),
        ],
        tasks=[
            Task(id="task1", tool="copy_file"),
            Task(
                id="task2",
                tool="process_data",
                dependencies=[TaskDependency(task_id="task1")],
            ),
        ],
        resources=ResourceLimits(memory_mb=8192),
        telemetry=TelemetryConfig(log_level="DEBUG", trace_enabled=True),
        environment={"DATA_DIR": "/data"},
        metadata={"owner": "data_team"},
    )
    assert spec.version == "1.1"
    assert spec.name == "data_processor"
    assert len(spec.permissions) == 1
    assert len(spec.tasks) == 2
    assert spec.resources.memory_mb == 8192
    assert spec.telemetry.log_level == "DEBUG"
    assert spec.environment["DATA_DIR"] == "/data"

    # Test invalid spec
    with pytest.raises(ValidationError):
        AgentSpec(name="test_agent")  # Missing tasks
    with pytest.raises(ValidationError):
        AgentSpec(tasks=[Task(id="task1", tool="echo")])  # Missing name


def test_validate_dsl():
    """Test DSL validation function."""
    # Test valid DSL
    data = {
        "name": "test_agent",
        "tasks": [
            {
                "id": "task1",
                "tool": "echo",
                "args": {"message": "hello"},
            }
        ],
    }
    spec = validate_dsl(data)
    assert isinstance(spec, AgentSpec)
    assert spec.name == "test_agent"

    # Test invalid DSL
    with pytest.raises(ValueError):
        validate_dsl({"name": "test_agent"})  # Missing tasks

    with pytest.raises(ValueError):
        validate_dsl(
            {
                "name": "test_agent",
                "tasks": [{"id": "task1"}],  # Missing tool
            }
        )
