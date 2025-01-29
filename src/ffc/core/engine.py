"""Agent runtime engine implementation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema import Permission
from .types import (
    AgentSpec,
    AgentState,
    AgentStatus,
    Tool,
    ToolResult,
)


@dataclass
class RuntimeError(Exception):
    """Base class for runtime errors."""

    message: str
    tool_name: str | None = None

    def __str__(self) -> str:
        if self.tool_name:
            return f"Runtime error in tool {self.tool_name}: {self.message}"
        return f"Runtime error: {self.message}"


class AgentRuntimeEngine:
    """A simplified Agent Runtime Engine that can execute agents based on
    their specifications.
    """

    def __init__(self, agent_spec: AgentSpec, working_dir: Path | None = None) -> None:
        """Initialize the agent runtime engine.

        Args:
            agent_spec: Agent specification
            working_dir: Working directory for the agent
        """
        if not isinstance(agent_spec, dict):
            raise RuntimeError("Invalid DSL: agent_spec must be a dictionary")
            
        if "tools" not in agent_spec:
            raise RuntimeError("Invalid DSL: missing required field 'tools'")

        self.agent_spec = agent_spec
        self.working_dir = working_dir or Path.cwd()
        self._tools: dict[str, Tool] = {}

        # Initialize security, resource tracking, and telemetry
        permissions = self._parse_permissions(agent_spec.get("permissions", []))
        resource_limits = agent_spec.get("resources")
        telemetry_config = agent_spec.get("telemetry")

        self._agent_state = AgentState(
            memory={},
            context={},
            state=AgentStatus.INITIALIZED,
            working_dir=self.working_dir,
            permissions=permissions,
            resources=resource_limits,
            telemetry=telemetry_config
        )

        self._initialize_tools()

    def _parse_permissions(self, permissions_data: list[dict[str, Any]]) -> list[Permission]:
        """Parse permissions from raw data.
        
        Args:
            permissions_data: List of permission dictionaries
            
        Returns:
            List of Permission objects
            
        Raises:
            RuntimeError: If permission data is invalid
        """
        try:
            permissions = []
            for p in permissions_data:
                if not isinstance(p, dict):
                    raise RuntimeError("Invalid permission format: must be a dictionary")
                    
                if "resource" not in p:
                    raise RuntimeError("Invalid permission: missing 'resource' field")
                    
                if "actions" not in p:
                    raise RuntimeError("Invalid permission: missing 'actions' field")
                    
                if not isinstance(p["actions"], list):
                    raise RuntimeError("Invalid permission: 'actions' must be a list")
                    
                permissions.append(Permission(
                    resource=p["resource"],
                    actions=p["actions"]
                ))
            return permissions
        except Exception as e:
            if not isinstance(e, RuntimeError):
                raise RuntimeError(f"Failed to parse permissions: {e}") from e
            raise

    def _initialize_tools(self) -> None:
        """Initialize tools from the agent specification."""
        for tool_spec in self.agent_spec.get("tools", []):
            if not isinstance(tool_spec, dict):
                raise RuntimeError("Invalid tool specification format")
                
            try:
                name = tool_spec["name"]
                tool_cls = tool_spec["clazz"]
                config = tool_spec.get("config", {})
                config["name"] = name

                permissions = self._parse_permissions(self.agent_spec.get("permissions", []))
                resource_limits = self.agent_spec.get("resources")
                telemetry_config = self.agent_spec.get("telemetry")

                self._tools[name] = tool_cls(
                    config=config,
                    permissions=permissions,
                    resource_limits=resource_limits,
                    telemetry_config=telemetry_config
                )
            except KeyError as e:
                raise RuntimeError(f"Invalid tool specification: missing required field {e}") from e
            except Exception as e:
                raise RuntimeError(f"Failed to initialize tool {name}: {e}") from e

    @classmethod
    def from_dsl(cls, dsl_data: dict[str, Any]) -> "AgentRuntimeEngine":
        """Create an engine instance from DSL data.
        
        Args:
            dsl_data: DSL data dictionary
            
        Returns:
            Initialized engine instance
            
        Raises:
            RuntimeError: If DSL validation fails
        """
        try:
            # Validate DSL structure
            if not isinstance(dsl_data, dict):
                raise RuntimeError("Invalid DSL: must be a dictionary")

            if "tools" not in dsl_data:
                raise RuntimeError("Invalid DSL: missing required field 'tools'")

            # Create engine instance
            return cls(dsl_data)
        except Exception as e:
            if not isinstance(e, RuntimeError):
                raise RuntimeError(f"Failed to parse DSL: {e}") from e
            raise

    def execute_tool(self, name: str, args: dict[str, str]) -> ToolResult:
        """Execute a tool by name with given arguments.
    
        Args:
            name: Tool name
            args: Tool arguments
    
        Returns:
            Tool execution results
    
        Raises:
            RuntimeError: If tool is not found or execution fails
        """
        if self._agent_state.state != AgentStatus.RUNNING:
            raise RuntimeError(f"Cannot execute tools in {self._agent_state.state.value} state")

        if name not in self._tools:
            raise RuntimeError(f"Tool {name} not found")

        try:
            return self._tools[name].execute(args, self._agent_state)
        except Exception as e:
            raise RuntimeError(str(e), name) from e

    def execute_dsl(self) -> list[ToolResult]:
        """Execute DSL commands in sequence.
        
        Returns:
            List of tool execution results
            
        Raises:
            RuntimeError: If any command execution fails
        """
        if self._agent_state.state != AgentStatus.RUNNING:
            raise RuntimeError(f"Cannot execute DSL in {self._agent_state.state.value} state")

        results = []
        commands = self.agent_spec.get("commands", [])
        
        if not isinstance(commands, list):
            raise RuntimeError("Invalid DSL: 'commands' must be a list")

        for command in commands:
            if not isinstance(command, dict):
                raise RuntimeError("Invalid command format: must be a dictionary")
                
            if "tool" not in command:
                raise RuntimeError("Invalid command format: missing 'tool' field")
                
            tool_name = command["tool"]
            args = command.get("args", {})
            
            if not isinstance(args, dict):
                raise RuntimeError(f"Invalid command format: 'args' for tool {tool_name} must be a dictionary")
                
            results.append(self.execute_tool(tool_name, args))
            
        return results

    def start(self) -> None:
        """Start the engine."""
        if self._agent_state.state == AgentStatus.INITIALIZED:
            self._agent_state.state = AgentStatus.RUNNING

    def stop(self) -> None:
        """Stop the engine."""
        if self._agent_state.state in (AgentStatus.RUNNING, AgentStatus.PAUSED):
            self._agent_state.state = AgentStatus.TERMINATED

    def pause(self) -> None:
        """Pause the engine."""
        if self._agent_state.state == AgentStatus.RUNNING:
            self._agent_state.state = AgentStatus.PAUSED

    def resume(self) -> None:
        """Resume the engine."""
        if self._agent_state.state == AgentStatus.PAUSED:
            self._agent_state.state = AgentStatus.RUNNING

    def update_memory(self, key: str, value: str) -> None:
        """Update agent memory.
        
        Args:
            key: Memory key
            value: Memory value
        """
        self._agent_state.memory[key] = value

    def update_context(self, key: str, value: str) -> None:
        """Update agent context.
        
        Args:
            key: Context key
            value: Context value
        """
        self._agent_state.context[key] = value

    def save_state(self) -> None:
        """Save the current agent state."""
        # TODO: Implement state persistence
        pass

    def load_state(self) -> None:
        """Load the agent state."""
        # TODO: Implement state loading
        pass

    @property
    def state(self) -> AgentState:
        """Get the current agent state."""
        return self._agent_state

    @property
    def is_running(self) -> bool:
        """Check if the engine is running."""
        return self._agent_state.state == AgentStatus.RUNNING
