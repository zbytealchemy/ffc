"""Unit tests for tool implementations."""


import pytest
from ffc.core.tools import BaseTool, Permission
from ffc.core.types import AgentState, AgentStatus, ToolResult


class SimpleTool(BaseTool):
    """Simple tool implementation for testing."""

    def _validate_inputs(self, args: dict[str, str]) -> None:
        """No validation needed for test tool."""
        pass

    def _execute_impl(self, args: dict[str, str], state: AgentState) -> ToolResult:
        return ToolResult(
            status="success",
            data={"args": args, "config": self.config},
            metadata={"tool": "simple"},
        )


class ErrorTool(BaseTool):
    """Tool that always raises an error."""

    def _validate_inputs(self, args: dict[str, str]) -> None:
        """No validation needed for test tool."""
        pass

    def _execute_impl(self, args: dict[str, str], state: AgentState) -> ToolResult:
        raise RuntimeError("Tool execution failed")


def test_base_tool_initialization():
    """Test BaseTool initialization."""
    config = {"name": "simple", "param": "value"}
    tool = SimpleTool(
        config, permissions=[Permission(resource="simple", actions=["execute"])]
    )
    assert tool.config == config


def test_tool_execution():
    """Test tool execution."""
    tool = SimpleTool(
        {"name": "simple", "param": "value"},
        permissions=[Permission(resource="simple", actions=["execute"])],
        resource_limits=None,  # Disable resource tracking
        telemetry_config=None  # Disable telemetry
    )
    state = AgentState(
        memory={},
        context={},
        state=AgentStatus.INITIALIZED,
        working_dir=None,
        permissions=None,
        resources=None,
        telemetry=None
    )
    args = {"input": "test"}

    result = tool.execute(args, state)
    assert result["status"] == "success"
    assert result["data"]["args"] == args
    assert result["data"]["config"] == {"name": "simple", "param": "value"}
    assert result["metadata"]["tool"] == "simple"


def test_tool_error_handling():
    """Test tool error handling."""
    tool = ErrorTool(
        {"name": "error"},
        permissions=[Permission(resource="error", actions=["execute"])],
        resource_limits=None,  # Disable resource tracking
        telemetry_config=None  # Disable telemetry
    )
    state = AgentState(
        memory={},
        context={},
        state=AgentStatus.INITIALIZED,
        working_dir=None,
        permissions=None,
        resources=None,
        telemetry=None
    )

    with pytest.raises(RuntimeError) as excinfo:
        tool.execute({}, state)
    assert str(excinfo.value) == "Tool execution failed"