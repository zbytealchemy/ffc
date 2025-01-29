"""Agent Orchestrator for managing distributed agent lifecycles."""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import aiohttp
from kubernetes import client, config  # type: ignore
from kubernetes.client import ApiException  # type: ignore

from .schema import Permission, ResourceLimits
from .types import AgentSpec, AgentStatus

logger = logging.getLogger(__name__)


@dataclass
class AgentMetadata:
    """Metadata about a running agent."""

    id: str
    name: str
    status: AgentStatus
    parent_id: Optional[str]
    children: List[str]  # List of child agent IDs
    spec: AgentSpec
    namespace: str
    created_at: str
    resource_limits: Optional[ResourceLimits]
    permissions: List[Permission] = field(default_factory=list)


class AgentOrchestrator:
    """Orchestrator for managing distributed agent lifecycles.

    Handles:
    - Agent deployment and lifecycle management
    - Parent-child relationships between agents
    - Resource allocation and limits
    - Permission inheritance and enforcement
    - Communication routing between agents
    """

    def __init__(
        self,
        namespace: str = "ffc-agents",
        agent_image: str = "ffc-agent-runtime:latest",
        registry_url: Optional[str] = None,
        local_mode: bool = False,  # Default to Kubernetes mode for tests
    ):
        """Initialize the orchestrator.

        Args:
            namespace: Kubernetes namespace for agents
            agent_image: Docker image for agent runtime
            registry_url: Optional private registry URL
            local_mode: If True, run in local mode without Kubernetes
        """
        self.local_mode = local_mode
        self.namespace = namespace
        self.agent_image = agent_image
        if registry_url:
            self.agent_image = f"{registry_url}/{agent_image}"

        # In-memory state of running agents
        self.agents: Dict[str, AgentMetadata] = {}

        if not local_mode:
            # Initialize Kubernetes client
            try:
                config.load_incluster_config()  # Try in-cluster config first
            except config.ConfigException:
                config.load_kube_config()  # Fall back to local config

            self.k8s_api = client.CoreV1Api()
            self.k8s_apps = client.AppsV1Api()
            self.k8s_core = client.CoreV1Api()

    async def _ensure_namespace(self) -> None:
        """Create namespace if it doesn't exist."""
        if not self.local_mode:
            try:
                await self.k8s_api.read_namespace(name=self.namespace)
            except ApiException as e:
                if e.status == 404:
                    ns = client.V1Namespace(
                        metadata=client.V1ObjectMeta(name=self.namespace)
                    )
                    await self.k8s_api.create_namespace(body=ns)

    async def deploy_agent(
        self, spec: AgentSpec, parent_id: Optional[str] = None
    ) -> str:
        """Deploy a new agent.

        Args:
            spec: Agent specification
            parent_id: Optional ID of parent agent

        Returns:
            ID of deployed agent

        Raises:
            ValueError: If parent agent not found
            RuntimeError: If deployment fails
        """
        # Generate unique ID and name for the agent
        agent_id = str(uuid.uuid4())
        agent_name = f"agent-{agent_id}"

        # Create agent metadata
        agent = AgentMetadata(
            id=agent_id,
            name=agent_name,
            status=AgentStatus.PENDING,
            parent_id=parent_id,
            children=[],
            spec=spec,
            namespace=self.namespace,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            resource_limits=None,
            # TODO: need better typing
            permissions=cast(list[Permission], spec.get("permissions", [])),
        )

        # Add to parent's children list
        if parent_id:
            if parent_id not in self.agents:
                raise ValueError(f"Parent agent {parent_id} not found")
            self.agents[parent_id].children.append(agent_id)

        # Add to agents map
        self.agents[agent_id] = agent

        if not self.local_mode:
            # Ensure namespace exists
            await self._ensure_namespace()

            # Create deployment
            deployment = client.V1Deployment(
                metadata=client.V1ObjectMeta(name=agent_name, namespace=self.namespace),
                spec=client.V1DeploymentSpec(
                    replicas=1,
                    selector=client.V1LabelSelector(match_labels={"app": agent_name}),
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(labels={"app": agent_name}),
                        spec=client.V1PodSpec(
                            containers=[
                                client.V1Container(
                                    name=agent_name,
                                    image=self.agent_image,
                                    env=[
                                        client.V1EnvVar(
                                            name="AGENT_SPEC", value=json.dumps(spec)
                                        )
                                    ],
                                )
                            ]
                        ),
                    ),
                ),
            )

            try:
                await self.k8s_apps.create_namespaced_deployment(
                    namespace=self.namespace, body=deployment
                )
            except ApiException as e:
                logger.error(f"Failed to create deployment: {e}")
                raise RuntimeError(f"Failed to create deployment: {e.reason}") from e

            try:
                # Create service
                service = client.V1Service(
                    metadata=client.V1ObjectMeta(
                        name=agent_name, namespace=self.namespace
                    ),
                    spec=client.V1ServiceSpec(
                        selector={"app": agent_name},
                        ports=[client.V1ServicePort(port=8080)],
                    ),
                )
                await self.k8s_core.create_namespaced_service(
                    namespace=self.namespace, body=service
                )
            except ApiException as e:
                logger.error(f"Failed to create service: {e}")
                raise RuntimeError(f"Failed to create service: {e.reason}") from e

        return agent_id

    async def _delete_agent_resources(self, agent: AgentMetadata) -> None:
        """Delete Kubernetes resources for an agent.

        Args:
            agent: Agent metadata
        """
        if not self.local_mode:
            try:
                # Delete service
                await self.k8s_api.delete_namespaced_service(
                    name=agent.name, namespace=self.namespace
                )
            except ApiException as e:
                if e.status != 404:  # Ignore if not found
                    logger.warning(
                        f"Failed to delete service for agent {agent.id}: {e}"
                    )

            try:
                # Delete deployment
                await self.k8s_apps.delete_namespaced_deployment(
                    name=agent.name, namespace=self.namespace
                )
            except ApiException as e:
                if e.status != 404:  # Ignore if not found
                    logger.warning(
                        f"Failed to delete deployment for agent {agent.id}: {e}"
                    )

    async def _terminate_children(self, children: List[str]) -> None:
        """Terminate child agents.

        Args:
            children: List of child agent IDs
        """
        for child_id in children:
            if child_id in self.agents:
                await self.terminate_agent(child_id)

    def _remove_from_parent(self, agent: AgentMetadata) -> None:
        """Remove agent from parent's children list.

        Args:
            agent: Agent metadata
        """
        if agent.parent_id and agent.parent_id in self.agents:
            parent = self.agents[agent.parent_id]
            if agent.id in parent.children:
                parent.children.remove(agent.id)

    async def terminate_agent(self, agent_id: str) -> None:
        """Terminate an agent.

        Args:
            agent_id: ID of agent to terminate
        """
        if agent_id not in self.agents:
            return

        agent = self.agents[agent_id]
        children = list(agent.children)  # Copy children list before modifying

        # Update status to TERMINATED first
        agent.status = AgentStatus.TERMINATED

        # Terminate children first
        await self._terminate_children(children)

        # Delete Kubernetes resources
        await self._delete_agent_resources(agent)

        # Remove from parent's children list
        self._remove_from_parent(agent)

    async def get_agent_status(self, agent_id: str) -> AgentStatus:
        """Get current status of an agent.

        Args:
            agent_id: ID of agent to check

        Returns:
            Current agent status

        Raises:
            ValueError: If agent not found
        """
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent = self.agents[agent_id]

        if not self.local_mode:
            try:
                deployment = await self.k8s_apps.read_namespaced_deployment_status(
                    name=agent.name, namespace=self.namespace
                )

                if getattr(deployment.status, "available_replicas", 0) == 1:
                    agent.status = AgentStatus.RUNNING
                elif getattr(deployment.status, "unavailable_replicas", 0) > 0:
                    agent.status = AgentStatus.FAILED
                else:
                    agent.status = AgentStatus.PENDING

            except ApiException as e:
                if e.status == 404:
                    agent.status = AgentStatus.TERMINATED
                else:
                    agent.status = AgentStatus.FAILED

        return agent.status

    async def execute_command(
        self, agent_id: str, command: str, timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute a command on an agent.

        Args:
            agent_id: Agent ID
            command: Command to execute
            timeout: Command timeout in seconds

        Returns:
            Command execution result

        Raises:
            ValueError: If agent not found
            RuntimeError: If agent is not running
        """
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent = self.agents[agent_id]
        if agent.status != AgentStatus.RUNNING:
            raise RuntimeError(
                f"Agent {agent_id} is not running (status: {agent.status.value})"
            )

        if self.local_mode:
            return {"status": "success", "output": "Command executed"}

        try:
            # Get service IP
            service = await self.k8s_core.read_namespaced_service(
                name=agent.name, namespace=self.namespace
            )
            ip = service.spec.cluster_ip

            # Execute command
            session = aiohttp.ClientSession()
            try:
                response = await session.post(
                    f"http://{ip}:8080/execute",
                    json={"command": command},
                    timeout=timeout,
                )
                result = await response.json()
                return result
            finally:
                await session.close()

        except Exception as e:
            raise RuntimeError(f"Command execution failed: {e!s}") from e

    def get_agent_tree(self, agent_id: str) -> Dict[str, Any]:
        """Get agent hierarchy tree starting from given agent.

        Args:
            agent_id: Root agent ID

        Returns:
            Dict representing agent tree structure

        Raises:
            ValueError: If agent not found
        """
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent = self.agents[agent_id]
        tree: Dict[str, Any] = {
            "id": agent.id,
            "name": agent.name,
            "status": agent.status.value,
            "children": [],
        }

        children: List[Dict[str, Any]] = tree["children"]  # type: ignore
        for child_id in agent.children:
            if child_id in self.agents:
                children.append(self.get_agent_tree(child_id))

        return tree
