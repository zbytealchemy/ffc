"""Tests for agent runner."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ffc.agent.runner import AgentRunner
from ffc.core.orchestrator import AgentOrchestrator
from ffc.core.schema import Permission
from ffc.core.tools import BaseTool
from ffc.core.types import AgentState, AgentStatus, ToolResult


class MockTool(BaseTool):
    """Mock tool for testing."""

    def _validate_inputs(self, args: dict[str, str]) -> None:
        """No validation needed for mock tool."""
        pass

    def _execute_impl(self, args: dict[str, str], state: AgentState) -> ToolResult:
        """Mock execution."""
        return ToolResult(status="success", data={"result": "test"}, metadata={})


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator for testing."""
    orchestrator = MagicMock(spec=AgentOrchestrator)
    # Make async methods
    orchestrator.deploy_agent = AsyncMock()
    orchestrator.terminate_agent = AsyncMock()
    orchestrator.get_agent_status = AsyncMock(return_value=AgentStatus.RUNNING)
    orchestrator.execute_command = AsyncMock(return_value={"status": "success"})
    return orchestrator


@pytest.fixture
def test_spec():
    """Test agent specification."""
    return {
        "name": "test-agent",
        "description": "Test agent",
        "permissions": [Permission(resource="files", actions=["read"])],
        "tools": [
            {
                "name": "file_reader",
                "config": {"name": "file_reader"},
                "clazz": MockTool,
            }
        ],
    }


@pytest.fixture
def test_spec_file(tmp_path, test_spec):
    """Create a test specification file."""
    # Convert Permission and ToolSpec objects to dict for JSON serialization
    json_spec = {
        "name": test_spec["name"],
        "description": test_spec["description"],
        "permissions": [
            {"resource": p.resource, "actions": p.actions}
            for p in test_spec["permissions"]
        ],
        "tools": [
            {"name": t["name"], "config": t["config"], "clazz": "MockTool"}
            for t in test_spec["tools"]
        ],
    }
    spec_file = tmp_path / "test_spec.json"
    spec_file.write_text(json.dumps(json_spec))
    return spec_file


@pytest.mark.asyncio
async def test_agent_runner_init(test_spec, mock_orchestrator):
    """Test AgentRunner initialization."""
    runner = AgentRunner(test_spec, orchestrator=mock_orchestrator, agent_id="test-123")

    # Compare everything except permissions which are converted to dicts
    assert runner.spec["name"] == test_spec["name"]
    assert runner.spec["description"] == test_spec["description"]
    assert runner.spec["tools"] == test_spec["tools"]
    assert runner.agent_id == "test-123"
    assert runner.orchestrator == mock_orchestrator
    assert "input_dir" in runner.state
    assert "output_dir" in runner.state
    assert "done_dir" in runner.state


@pytest.mark.asyncio
async def test_agent_runner_from_file(test_spec_file, mock_orchestrator):
    """Test creating AgentRunner from file."""
    # Mock the tool class resolution
    with patch("ffc.agent.runner.globals", return_value={"MockTool": MockTool}):
        runner = await AgentRunner.from_file(
            test_spec_file, orchestrator=mock_orchestrator
        )

        assert runner.spec["name"] == "test-agent"
        assert isinstance(runner.spec["permissions"], list)
        assert isinstance(runner.spec["permissions"][0], dict)
        assert runner.spec["permissions"][0]["resource"] == "files"
        assert runner.spec["permissions"][0]["actions"] == ["read"]
        assert runner.orchestrator == mock_orchestrator
        assert "input_dir" in runner.state
        assert "output_dir" in runner.state
        assert "done_dir" in runner.state


@pytest.mark.asyncio
async def test_agent_runner_start_stop(test_spec, mock_orchestrator):
    """Test starting and stopping agent runner."""
    runner = AgentRunner(test_spec, orchestrator=mock_orchestrator, agent_id="test-123")

    await runner.start()
    # Don't compare the exact spec since permissions are converted to dicts
    assert mock_orchestrator.deploy_agent.call_count == 1
    assert mock_orchestrator.deploy_agent.call_args[0][0] == "test-123"
    called_spec = mock_orchestrator.deploy_agent.call_args[0][1]
    assert called_spec["name"] == test_spec["name"]
    assert called_spec["description"] == test_spec["description"]
    assert called_spec["tools"] == test_spec["tools"]

    await runner.stop()
    mock_orchestrator.terminate_agent.assert_called_once_with("test-123")


@pytest.mark.asyncio
async def test_agent_runner_execute_command(test_spec, mock_orchestrator):
    """Test command execution."""
    runner = AgentRunner(test_spec, orchestrator=mock_orchestrator, agent_id="test-123")

    result = await runner.execute_command("test command")
    mock_orchestrator.execute_command.assert_called_once_with("test-123", "test command")
    assert result == {"status": "success"}


@pytest.mark.asyncio
async def test_agent_runner_get_status(test_spec, mock_orchestrator):
    """Test getting agent status."""
    runner = AgentRunner(test_spec, orchestrator=mock_orchestrator, agent_id="test-123")

    status = await runner.get_status()
    mock_orchestrator.get_agent_status.assert_called_once_with("test-123")
    assert status == AgentStatus.RUNNING


# TODO: Test child agent creation - refactor
@pytest.mark.asyncio
async def create_child_agent(test_spec, mock_orchestrator):
    """Test creating child agent through CreateAgentTool."""
    runner = AgentRunner(
        test_spec, orchestrator=mock_orchestrator, agent_id="parent-123"
    )

    await runner.start()

    # Get the CreateAgentTool instance
    create_tool = runner.engine._tools["create_agent"]

    # Test executing the tool
    child_spec = {
        "name": "child-agent",
        "description": "Test child agent",
        "permissions": [{"resource": "files", "actions": ["read"]}],
        "tools": [
            {
                "name": "file_reader",
                "config": {"name": "file_reader"},
                "clazz": "MockTool",
            }
        ],
    }

    mock_orchestrator.deploy_agent.return_value = "child-456"

    result = await create_tool.execute({"spec": json.dumps(child_spec)}, {})

    assert result["status"] == "success"
    assert result["data"]["agent_id"] == "child-456"
    mock_orchestrator.deploy_agent.assert_awaited_once_with(
        child_spec, parent_id="parent-123"
    )

    await runner.stop()
