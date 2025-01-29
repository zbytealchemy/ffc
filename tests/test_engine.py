"""Unit tests for runtime engine."""


import pytest
from ffc.core.engine import AgentRuntimeEngine, RuntimeError
from ffc.core.tools import BaseTool
from ffc.core.types import (
    AgentState,
    AgentStatus,
    ToolResult,
)


class MockTool(BaseTool):
    """Mock tool for testing."""

    def _validate_inputs(self, args: dict[str, str]) -> None:
        """No validation needed for mock tool."""
        pass

    def _execute_impl(self, args: dict[str, str], state: AgentState) -> ToolResult:
        return {
            "status": "success",
            "data": {"args": args},
            "metadata": {"tool": "mock_tool"},
        }


class ErrorTool(BaseTool):
    """Tool that raises an error for testing."""

    def _validate_inputs(self, args: dict[str, str]) -> None:
        """No validation needed for test tool."""
        pass

    def _execute_impl(self, args: dict[str, str], state: AgentState) -> ToolResult:
        raise RuntimeError("Test error", "error_tool")


def test_engine_initialization():
    """Test engine initialization."""
    spec = {
        "tools": [{"name": "test", "config": {}, "clazz": MockTool}],
        "permissions": [{"resource": "test", "actions": ["execute"]}]
    }
    engine = AgentRuntimeEngine(spec)
    assert engine.state.state == AgentStatus.INITIALIZED
    assert not engine.is_running


def test_engine_invalid_spec():
    """Test engine initialization with invalid spec."""
    # Test empty spec
    with pytest.raises(RuntimeError) as exc:
        AgentRuntimeEngine({})
    assert str(exc.value) == "Runtime error: Invalid DSL: missing required field 'tools'"
    
    # Test non-dict spec
    with pytest.raises(RuntimeError) as exc:
        AgentRuntimeEngine([])
    assert str(exc.value) == "Runtime error: Invalid DSL: agent_spec must be a dictionary"


def test_engine_start_stop():
    """Test engine start/stop functionality."""
    spec = {
        "tools": [{"name": "test", "config": {}, "clazz": MockTool}],
        "permissions": [{"resource": "test", "actions": ["execute"]}]
    }
    engine = AgentRuntimeEngine(spec)
    
    # Test start
    engine.start()
    assert engine.state.state == AgentStatus.RUNNING
    assert engine.is_running
    
    # Test stop
    engine.stop()
    assert engine.state.state == AgentStatus.TERMINATED
    assert not engine.is_running


def test_engine_pause_resume():
    """Test engine pause/resume functionality."""
    spec = {
        "tools": [{"name": "test", "config": {}, "clazz": MockTool}],
        "permissions": [{"resource": "test", "actions": ["execute"]}]
    }
    engine = AgentRuntimeEngine(spec)
    
    # Start engine
    engine.start()
    assert engine.is_running
    
    # Test pause
    engine.pause()
    assert engine.state.state == AgentStatus.PAUSED
    assert not engine.is_running
    
    # Test resume
    engine.resume()
    assert engine.state.state == AgentStatus.RUNNING
    assert engine.is_running


def test_tool_execution():
    """Test tool execution."""
    spec = {
        "tools": [{"name": "test", "config": {}, "clazz": MockTool}],
        "permissions": [{"resource": "test", "actions": ["execute"]}]
    }
    engine = AgentRuntimeEngine(spec)
    engine.start()
    
    result = engine.execute_tool("test", {})
    assert result["status"] == "success"
    assert result["data"]["args"] == {}


def test_tool_execution_errors():
    """Test tool execution error cases."""
    spec = {
        "tools": [{"name": "test", "config": {}, "clazz": MockTool}],
        "permissions": [{"resource": "test", "actions": ["execute"]}]
    }
    engine = AgentRuntimeEngine(spec)
    
    # Test executing tool before starting engine
    with pytest.raises(RuntimeError) as exc:
        engine.execute_tool("test", {})
    assert str(exc.value) == "Runtime error: Cannot execute tools in initialized state"
    
    # Test executing non-existent tool
    engine.start()
    with pytest.raises(RuntimeError) as exc:
        engine.execute_tool("nonexistent_tool", {})
    assert str(exc.value) == "Runtime error: Tool nonexistent_tool not found"


def test_dsl_execution():
    """Test DSL execution."""
    dsl = {
        "tools": [{"name": "test", "config": {}, "clazz": MockTool}],
        "commands": [{"tool": "test", "args": {}}],
        "permissions": [{"resource": "test", "actions": ["execute"]}]
    }
    engine = AgentRuntimeEngine.from_dsl(dsl)
    engine.start()
    
    results = engine.execute_dsl()
    assert len(results) == 1
    assert results[0]["status"] == "success"
    assert results[0]["data"]["args"] == {}


def test_dsl_execution_errors():
    """Test DSL execution error cases."""
    # Test missing tool field
    dsl = {
        "tools": [{"name": "test", "config": {}, "clazz": MockTool}],
        "commands": [{"args": {}}],
        "permissions": [{"resource": "test", "actions": ["execute"]}]
    }
    engine = AgentRuntimeEngine.from_dsl(dsl)
    engine.start()
    
    with pytest.raises(RuntimeError) as exc:
        engine.execute_dsl()
    assert str(exc.value) == "Runtime error: Invalid command format: missing 'tool' field"
    
    # Test invalid commands format
    dsl = {
        "tools": [{"name": "test", "config": {}, "clazz": MockTool}],
        "commands": "invalid",
        "permissions": [{"resource": "test", "actions": ["execute"]}]
    }
    engine = AgentRuntimeEngine.from_dsl(dsl)
    engine.start()
    
    with pytest.raises(RuntimeError) as exc:
        engine.execute_dsl()
    assert str(exc.value) == "Runtime error: Invalid DSL: 'commands' must be a list"
    
    # Test invalid command args
    dsl = {
        "tools": [{"name": "test", "config": {}, "clazz": MockTool}],
        "commands": [{"tool": "test", "args": "invalid"}],
        "permissions": [{"resource": "test", "actions": ["execute"]}]
    }
    engine = AgentRuntimeEngine.from_dsl(dsl)
    engine.start()
    
    with pytest.raises(RuntimeError) as exc:
        engine.execute_dsl()
    assert str(exc.value) == "Runtime error: Invalid command format: 'args' for tool test must be a dictionary"


def test_state_management():
    """Test state management functionality."""
    spec = {
        "tools": [{"name": "test", "config": {}, "clazz": MockTool}],
        "permissions": [{"resource": "test", "actions": ["execute"]}]
    }
    engine = AgentRuntimeEngine(spec)
    
    # Test memory updates
    engine.update_memory("test_key", "test_value")
    assert engine.state.memory["test_key"] == "test_value"
    
    # Test context updates
    engine.update_context("test_key", "test_value")
    assert engine.state.context["test_key"] == "test_value"


def test_engine_invalid_state_transitions():
    """Test invalid state transitions."""
    engine = AgentRuntimeEngine({"tools": []})

    # Test executing tool in initialized state
    with pytest.raises(RuntimeError, match="Runtime error: Cannot execute tools in initialized state"):
        engine.execute_tool("test", {})

    # Test executing DSL in initialized state
    with pytest.raises(RuntimeError, match="Runtime error: Cannot execute DSL in initialized state"):
        engine.execute_dsl()
