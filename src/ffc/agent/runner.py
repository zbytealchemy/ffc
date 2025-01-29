"""
Agent runner implementation for executing agent specifications.
"""

import importlib
import json
import sys
from pathlib import Path
from typing import Any, Optional

from ..core.engine import AgentRuntimeEngine
from ..core.orchestrator import AgentOrchestrator, AgentStatus
from ..core.schema import Permission, TelemetryConfig
from ..core.types import AgentSpec, ToolResult


class AgentRunner:
    """Runner for executing agent specifications."""

    def __init__(
        self,
        spec: AgentSpec,
        working_dir: Path | None = None,
        agent_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        orchestrator: Optional[AgentOrchestrator] = None,
    ):
        """Initialize the agent runner.

        Args:
            spec: Agent specification dictionary
            working_dir: Optional working directory for the agent
            agent_id: Optional ID for this agent (provided by orchestrator)
            parent_id: Optional ID of parent agent
            orchestrator: Optional orchestrator instance for managing child agents
        """
        if "permissions" in spec:
            spec = spec.copy()  # Make a copy to avoid modifying the original
            spec["permissions"] = [
                {"resource": p.resource, "actions": p.actions} if hasattr(p, "resource")
                else p
                for p in spec["permissions"]
            ]

        self.spec = spec
        self.working_dir = working_dir or Path.cwd()
        self.agent_id = agent_id
        self.parent_id = parent_id

        self.state = {
            "input_dir": str(self.working_dir / "input"),
            "output_dir": str(self.working_dir / "output"),
            "done_dir": str(self.working_dir / "done"),
        }
        self.engine = AgentRuntimeEngine(spec, working_dir)

        if orchestrator:
            self.orchestrator = orchestrator
        else:
            # When running as a container, create orchestrator with in-cluster config
            self.orchestrator = AgentOrchestrator()

    @classmethod
    async def from_file(
        cls, spec_path: Path, orchestrator: Optional[AgentOrchestrator] = None
    ) -> "AgentRunner":
        """Create an agent runner from a specification file.

        Args:
            spec_path: Path to specification file
            orchestrator: Optional orchestrator instance

        Returns:
            Initialized agent runner
        """
        with open(spec_path) as f:
            spec = json.load(f)

        # Convert tool class names to actual classes
        if "tools" in spec:
            for tool_spec in spec["tools"]:
                if isinstance(tool_spec["clazz"], str):
                    try:
                        if "." in tool_spec["clazz"]:
                            module_path, class_name = tool_spec["clazz"].rsplit(".", 1)
                            module = importlib.import_module(module_path)
                            tool_class = getattr(module, class_name)
                        else:
                            tool_class = globals()[tool_spec["clazz"]]
                        tool_spec["clazz"] = tool_class
                    except (ImportError, AttributeError, KeyError) as e:
                        raise ValueError(
                            f"Tool class {tool_spec['clazz']} not found: {e}"
                        ) from e

        if "permissions" in spec:
            spec["permissions"] = [
                Permission(resource=p["resource"], actions=p["actions"])
                for p in spec["permissions"]
            ]

        if "telemetry" in spec:
            spec["telemetry"] = TelemetryConfig(**spec["telemetry"])

        if "permissions" in spec:
            spec = spec.copy()  
            spec["permissions"] = [
                {"resource": p.resource, "actions": p.actions} if hasattr(p, "resource")
                else p
                for p in spec["permissions"]
            ]

        return cls(spec, working_dir=spec_path.parent, orchestrator=orchestrator)

    async def run(self) -> None:
        """Run the agent."""
        try:
            await self.start()
            input_dir = Path(self.state["input_dir"])
            output_dir = Path(self.state["output_dir"])
            done_dir = Path(self.state["done_dir"])

            for file_path in input_dir.glob("*"):
                if file_path.is_file():
                    result = await self.execute_command(
                        f'file_reader file_path="{file_path!s}"'
                    )
                    if not result or result.get("status") != "success":
                        print(
                            f"Error reading file {file_path}: {result.get('metadata', {}).get('error', 'Unknown error') if result else 'Unknown error'}"
                        )
                        continue

                    content = result["data"]["content"].upper()
                    output_path = output_dir / file_path.name

                    result = await self.execute_command(
                        f'file_writer file_path="{output_path!s}" content="{content}"'
                    )
                    if not result or result.get("status") != "success":
                        print(
                            f"Error writing file {output_path}: {result.get('metadata', {}).get('error', 'Unknown error') if result else 'Unknown error'}"
                        )
                        continue

                    done_path = done_dir / file_path.name
                    result = await self.execute_command(
                        f'file_mover source="{file_path!s}" destination="{done_path!s}"'
                    )
                    if not result or result.get("status") != "success":
                        print(
                            f"Error moving file {file_path}: {result.get('metadata', {}).get('error', 'Unknown error') if result else 'Unknown error'}"
                        )
                        continue

                    print(f"Successfully processed {file_path}")

            await self.stop()
        except Exception as e:
            print(f"Error running agent: {e!s}", file=sys.stderr)
            raise

    async def start(self) -> None:
        """Start the agent runner."""
        if self.orchestrator and self.agent_id:
            await self.orchestrator.deploy_agent(self.agent_id, self.spec)
        else:
            self.engine.start()

        # Register tool for creating child agents
        # TODO: Move this to orchestrator
        # self.engine.register_tool(
        #     "create_agent", CreateAgentTool(self.orchestrator, self.agent_id)
        # )

    async def stop(self) -> None:
        """Stop the agent runner."""
        if self.orchestrator and self.agent_id:
            await self.orchestrator.terminate_agent(self.agent_id)
        else:
            self.engine.stop()

    async def execute_command(self, command: str) -> ToolResult:
        """Execute a command using the runtime engine.

        Args:
            command: Command to execute

        Returns:
            Command execution result
        """
        return await self.orchestrator.execute_command(self.agent_id, command)

    async def execute_file(self, command_file: str | Path) -> list[Any]:
        """Execute commands from a file.

        Args:
            command_file: Path to file containing commands

        Returns:
            List of command execution results

        Raises:
            FileNotFoundError: If command file doesn't exist
        """
        file_path = Path(command_file)
        if not file_path.exists():
            raise FileNotFoundError(f"Command file not found: {command_file}")

        results = []
        with open(file_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    result = await self.execute_command(line)
                    results.append(result)

        return results

    async def get_status(self) -> AgentStatus:
        """Get current agent status from orchestrator."""
        if self.orchestrator and self.agent_id:
            return await self.orchestrator.get_agent_status(self.agent_id)
        return AgentStatus.RUNNING  # Default status when no orchestrator


class CreateAgentTool:
    """Tool for creating child agents through the orchestrator."""

    def __init__(self, orchestrator: AgentOrchestrator, parent_id: Optional[str]):
        self.orchestrator = orchestrator
        self.parent_id = parent_id

    async def execute(self, args: dict[str, str], state: Any) -> ToolResult:
        """Execute the tool.

        Args:
            args: Must contain 'spec' with agent specification
            state: Current agent state

        Returns:
            Tool execution result with child agent ID
        """
        try:
            spec = json.loads(args["spec"])
            child_id = await self.orchestrator.deploy_agent(
                spec, parent_id=self.parent_id
            )

            return {
                "status": "success",
                "data": {"agent_id": child_id},
                "metadata": {"tool": "create_agent"},
            }
        except Exception as e:
            return {
                "status": "error",
                "data": {"error": str(e)},
                "metadata": {"tool": "create_agent"},
            }
