"""Unit tests for type definitions."""


from ffc.core.types import AgentSpec, AgentState, AgentStatus, ToolResult, ToolSpec


def test_tool_spec_creation():
    """Test creation of ToolSpec."""
    tool_spec = ToolSpec(name="test_tool", config={"param": "value"}, clazz=None)
    assert tool_spec["name"] == "test_tool"
    assert tool_spec["config"] == {"param": "value"}
    assert tool_spec["clazz"] is None


def test_agent_spec_creation():
    """Test creation of AgentSpec."""
    tool_spec = ToolSpec(name="test_tool", config={}, clazz=None)
    agent_spec = AgentSpec(tools=[tool_spec])
    assert len(agent_spec["tools"]) == 1
    assert agent_spec["tools"][0] == tool_spec


def test_agent_state_creation():
    """Test creation of AgentState."""
    state = AgentState(
        memory={"key": "value"},
        context={"ctx": "data"},
        state=AgentStatus.INITIALIZED,
        working_dir=None,
        permissions=None,
        resources=None,
        telemetry=None
    )
    assert state.memory == {"key": "value"}
    assert state.context == {"ctx": "data"}
    assert state.state == AgentStatus.INITIALIZED


def test_agent_status_values():
    """Test AgentStatus values."""
    assert AgentStatus.PENDING.value == "pending"
    assert AgentStatus.INITIALIZED.value == "initialized"
    assert AgentStatus.RUNNING.value == "running"
    assert AgentStatus.PAUSED.value == "paused"
    assert AgentStatus.COMPLETED.value == "completed"
    assert AgentStatus.FAILED.value == "failed"
    assert AgentStatus.TERMINATED.value == "terminated"


def test_tool_result_creation():
    """Test creation of ToolResult."""
    result = ToolResult(
        status="success",
        data={"output": "test"},
        metadata={"duration": 1.0}
    )
    assert result["status"] == "success"
    assert result["data"] == {"output": "test"}
    assert result["metadata"] == {"duration": 1.0}
