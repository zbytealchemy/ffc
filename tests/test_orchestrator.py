"""Tests for the AgentOrchestrator."""

from unittest.mock import AsyncMock, patch

import pytest
from ffc.core.orchestrator import AgentOrchestrator, AgentStatus
from kubernetes.client import ApiException  # type: ignore


@pytest.fixture
def mock_k8s_apis():
    """Mock Kubernetes API clients."""
    with patch("kubernetes.config.load_kube_config"), patch(
        "kubernetes.client.CoreV1Api"
    ) as mock_core, patch("kubernetes.client.AppsV1Api") as mock_apps:
        mock_core_api = AsyncMock()
        mock_apps_api = AsyncMock()

        mock_core.return_value = mock_core_api
        mock_apps.return_value = mock_apps_api

        yield mock_core_api, mock_apps_api


@pytest.fixture
def orchestrator(mock_k8s_apis):
    """Create AgentOrchestrator instance with mocked APIs."""
    return AgentOrchestrator(local_mode=False)


@pytest.mark.asyncio
async def test_deploy_agent_basic(orchestrator, mock_k8s_apis):
    """Test deploying a new agent with basic configuration."""
    mock_core_api, mock_apps_api = mock_k8s_apis

    # Basic agent spec
    spec = {"name": "test-agent", "type": "test", "config": {}}

    # Deploy agent
    agent_id = await orchestrator.deploy_agent(spec)

    # Verify agent is registered
    assert agent_id in orchestrator.agents
    assert orchestrator.agents[agent_id].name == f"agent-{agent_id}"

    # Verify Kubernetes API calls
    mock_apps_api.create_namespaced_deployment.assert_called_once()
    mock_core_api.create_namespaced_service.assert_called_once()


@pytest.mark.asyncio
async def test_terminate_agent(orchestrator, mock_k8s_apis):
    """Test terminating an agent."""
    mock_core_api, mock_apps_api = mock_k8s_apis

    # Deploy agent first
    spec = {"name": "test-agent", "type": "test", "config": {}}
    agent_id = await orchestrator.deploy_agent(spec)

    # Reset mock call counts
    mock_core_api.delete_namespaced_service.reset_mock()
    mock_apps_api.delete_namespaced_deployment.reset_mock()

    # Terminate agent
    await orchestrator.terminate_agent(agent_id)

    # Verify agent status is updated
    assert agent_id in orchestrator.agents
    assert orchestrator.agents[agent_id].status == AgentStatus.TERMINATED

    # Verify Kubernetes API calls
    mock_core_api.delete_namespaced_service.assert_called_once()
    mock_apps_api.delete_namespaced_deployment.assert_called_once()


@pytest.mark.asyncio
async def test_deploy_child_agent(orchestrator, mock_k8s_apis):
    """Test deploying a child agent."""
    mock_core_api, mock_apps_api = mock_k8s_apis

    # Deploy parent agent
    parent_spec = {"name": "parent-agent", "type": "test", "config": {}}
    parent_id = await orchestrator.deploy_agent(parent_spec)

    # Deploy child agent
    child_spec = {"name": "child-agent", "type": "test", "config": {}}
    child_id = await orchestrator.deploy_agent(child_spec, parent_id=parent_id)

    # Verify parent-child relationship
    assert child_id in orchestrator.agents[parent_id].children
    assert orchestrator.agents[child_id].parent_id == parent_id

    # Verify child inherits parent's permissions
    assert (
        orchestrator.agents[child_id].permissions
        == orchestrator.agents[parent_id].permissions
    )


@pytest.mark.asyncio
async def test_terminate_agent_with_children(orchestrator, mock_k8s_apis):
    """Test terminating an agent with children."""
    mock_core_api, mock_apps_api = mock_k8s_apis

    # Mock deployment status for RUNNING
    mock_deployment = AsyncMock()
    mock_deployment.status.available_replicas = 1
    mock_deployment.status.unavailable_replicas = None
    mock_apps_api.read_namespaced_deployment_status.return_value = mock_deployment

    # Deploy parent agent
    parent_spec = {"name": "parent-agent", "type": "test", "config": {}}
    parent_id = await orchestrator.deploy_agent(parent_spec)
    await orchestrator.get_agent_status(parent_id)  # Wait for status to be updated

    # Deploy child agents
    child_ids = []
    for i in range(2):
        child_spec = {"name": f"child-agent-{i}", "type": "test", "config": {}}
        child_id = await orchestrator.deploy_agent(child_spec, parent_id=parent_id)
        await orchestrator.get_agent_status(child_id)  # Wait for status to be updated
        child_ids.append(child_id)

    # Reset mock call counts
    mock_core_api.delete_namespaced_service.reset_mock()
    mock_apps_api.delete_namespaced_deployment.reset_mock()

    # Mock deployment status for TERMINATED
    mock_apps_api.read_namespaced_deployment_status.side_effect = ApiException(
        status=404
    )

    # Terminate parent agent
    await orchestrator.terminate_agent(parent_id)

    # Wait for all agents to be terminated
    await orchestrator.get_agent_status(parent_id)
    for child_id in child_ids:
        await orchestrator.get_agent_status(child_id)

    # Verify all agents are terminated
    assert orchestrator.agents[parent_id].status == AgentStatus.TERMINATED
    for child_id in child_ids:
        assert orchestrator.agents[child_id].status == AgentStatus.TERMINATED

    # Verify all services and deployments are deleted
    expected_service_names = {
        f"agent-{agent_id}" for agent_id in [parent_id, *child_ids]
    }
    actual_service_names = {
        call.kwargs["name"]
        for call in mock_core_api.delete_namespaced_service.mock_calls
    }
    print(f"Expected service names: {expected_service_names}")
    print(f"Actual service names: {actual_service_names}")
    assert mock_core_api.delete_namespaced_service.call_count == 3

    # Verify all expected service and deployment deletions were called
    assert actual_service_names == expected_service_names

    expected_deployment_names = {
        f"agent-{agent_id}" for agent_id in [parent_id, *child_ids]
    }
    actual_deployment_names = {
        call.kwargs["name"]
        for call in mock_apps_api.delete_namespaced_deployment.mock_calls
    }
    assert actual_deployment_names == expected_deployment_names


@pytest.mark.asyncio
async def test_get_agent_status(orchestrator, mock_k8s_apis):
    """Test getting agent status."""
    mock_core_api, mock_apps_api = mock_k8s_apis

    # Deploy an agent
    spec = {"name": "test-agent", "type": "test", "config": {}}
    agent_id = await orchestrator.deploy_agent(spec)

    # Mock deployment status for RUNNING
    mock_deployment = AsyncMock()
    mock_deployment.status.available_replicas = 1
    mock_deployment.status.unavailable_replicas = None
    mock_apps_api.read_namespaced_deployment_status.return_value = mock_deployment

    # Test RUNNING status
    status = await orchestrator.get_agent_status(agent_id)
    assert status == AgentStatus.RUNNING
    assert orchestrator.agents[agent_id].status == AgentStatus.RUNNING

    # Mock deployment status for FAILED
    mock_deployment.status.available_replicas = 0
    mock_deployment.status.unavailable_replicas = 1
    status = await orchestrator.get_agent_status(agent_id)
    assert status == AgentStatus.FAILED
    assert orchestrator.agents[agent_id].status == AgentStatus.FAILED

    # Mock deployment status for PENDING
    mock_deployment.status.available_replicas = 0
    mock_deployment.status.unavailable_replicas = 0
    status = await orchestrator.get_agent_status(agent_id)
    assert status == AgentStatus.PENDING
    assert orchestrator.agents[agent_id].status == AgentStatus.PENDING

    # Test non-existent agent
    with pytest.raises(ValueError, match="Agent not-found not found"):
        await orchestrator.get_agent_status("not-found")


@pytest.mark.asyncio
async def test_get_agent_tree(orchestrator, mock_k8s_apis):
    """Test getting agent hierarchy tree."""
    mock_core_api, mock_apps_api = mock_k8s_apis

    # Deploy parent agent
    parent_spec = {"name": "parent-agent", "type": "test", "config": {}}
    parent_id = await orchestrator.deploy_agent(parent_spec)

    # Deploy child agents
    child_ids = []
    for i in range(2):
        child_spec = {"name": f"child-agent-{i}", "type": "test", "config": {}}
        child_id = await orchestrator.deploy_agent(child_spec, parent_id=parent_id)
        child_ids.append(child_id)

    # Get agent tree
    tree = orchestrator.get_agent_tree(parent_id)

    # Verify tree structure
    assert tree["id"] == parent_id
    assert tree["name"] == f"agent-{parent_id}"
    assert tree["status"] == AgentStatus.PENDING.value
    assert len(tree["children"]) == 2

    # Verify child nodes
    for child in tree["children"]:
        assert child["id"] in child_ids
        assert child["name"].startswith("agent-")
        assert child["status"] == AgentStatus.PENDING.value
        assert child["children"] == []

    # Test non-existent agent
    with pytest.raises(ValueError, match="Agent not-found not found"):
        orchestrator.get_agent_tree("not-found")


@pytest.mark.asyncio
async def test_execute_command(orchestrator, mock_k8s_apis):
    """Test executing a command on an agent."""
    mock_core_api, mock_apps_api = mock_k8s_apis

    # Deploy an agent
    spec = {"name": "test-agent", "type": "test", "config": {}}
    agent_id = await orchestrator.deploy_agent(spec)

    # Mock deployment status for RUNNING
    mock_deployment = AsyncMock()
    mock_deployment.status.available_replicas = 1
    mock_deployment.status.unavailable_replicas = None
    mock_apps_api.read_namespaced_deployment_status.return_value = mock_deployment

    # Wait for agent to be running
    await orchestrator.get_agent_status(agent_id)

    # Mock service response
    mock_service = AsyncMock()
    mock_service.spec.cluster_ip = "10.0.0.1"
    mock_core_api.read_namespaced_service.return_value = mock_service

    # Mock aiohttp client session
    mock_response = AsyncMock()
    mock_response.json.return_value = {"status": "success", "output": "command output"}
    mock_response.status = 200

    mock_session = AsyncMock()
    mock_session.post.return_value = mock_response
    mock_session.close = AsyncMock()

    with patch("aiohttp.ClientSession", return_value=mock_session):
        # Execute command
        result = await orchestrator.execute_command(agent_id, "test command")
        assert result == {"status": "success", "output": "command output"}

    # Test non-existent agent
    with pytest.raises(ValueError, match="Agent not-found not found"):
        await orchestrator.execute_command("not-found", "test command")

    # Test agent not running
    orchestrator.agents[agent_id].status = AgentStatus.FAILED
    with pytest.raises(
        RuntimeError, match=f"Agent {agent_id} is not running \\(status: failed\\)"
    ):
        await orchestrator.execute_command(agent_id, "test command")


@pytest.mark.asyncio
async def test_deploy_agent_error_handling(orchestrator, mock_k8s_apis):
    """Test error handling during agent deployment."""
    mock_core_api, mock_apps_api = mock_k8s_apis

    # Test deployment creation failure
    mock_apps_api.create_namespaced_deployment.side_effect = ApiException(
        status=400, reason="Deployment creation failed"
    )
    spec = {"name": "test-agent", "type": "test", "config": {}}
    with pytest.raises(
        RuntimeError, match="Failed to create deployment: Deployment creation failed"
    ):
        await orchestrator.deploy_agent(spec)

    # Test service creation failure
    mock_apps_api.create_namespaced_deployment.side_effect = None
    mock_core_api.create_namespaced_service.side_effect = ApiException(
        status=400, reason="Service creation failed"
    )
    with pytest.raises(
        RuntimeError, match="Failed to create service: Service creation failed"
    ):
        await orchestrator.deploy_agent(spec)


@pytest.mark.asyncio
async def test_terminate_agent_error_handling(orchestrator, mock_k8s_apis):
    """Test error handling in terminate_agent."""
    mock_core_api, mock_apps_api = mock_k8s_apis

    # Deploy agent
    spec = {"name": "test-agent", "type": "test", "config": {}}
    agent_id = await orchestrator.deploy_agent(spec)

    # Test service deletion failure
    mock_core_api.delete_namespaced_service.side_effect = ApiException(
        status=500, reason="Service deletion failed"
    )
    await orchestrator.terminate_agent(agent_id)  # Should log error but not raise

    # Verify agent status is still updated
    assert orchestrator.agents[agent_id].status == AgentStatus.TERMINATED

    # Test deployment deletion failure
    mock_apps_api.delete_namespaced_deployment.side_effect = ApiException(
        status=500, reason="Deployment deletion failed"
    )
    await orchestrator.terminate_agent(agent_id)  # Should log error but not raise

    # Verify agent status is still updated
    assert orchestrator.agents[agent_id].status == AgentStatus.TERMINATED

    # Test terminating non-existent agent
    await orchestrator.terminate_agent("not-found")  # Should return silently
