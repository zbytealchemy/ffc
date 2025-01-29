"""Base agent implementation that defines the core agent interface."""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from .types import AgentStatus, Tool, ToolResult


class ResourceLimits(BaseModel):
    """Resource limits for task execution."""
    memory_mb: int = Field(default=1024, description="Memory limit in MB", gt=0)
    cpu_cores: float = Field(default=1.0, description="CPU cores limit")
    timeout_sec: int = Field(default=300, description="Timeout in seconds", gt=0)

class Permission(BaseModel):
    """Permission definition for tools and resources."""
    resource: str = Field(..., description="Resource identifier")
    actions: list[str] = Field(..., description="Allowed actions")
    conditions: dict[str, Any] | None = Field(default=None, description="Additional conditions")

class TelemetryConfig(BaseModel):
    """Telemetry configuration."""
    enabled: bool = Field(default=True, description="Enable telemetry collection")
    log_level: str = Field(default="INFO", description="Logging level")
    metrics: list[str] = Field(default_factory=list, description="Metrics to collect")
    trace_enabled: bool = Field(default=False, description="Enable distributed tracing")

@dataclass
class AgentContext:
    """Context information for an agent."""
    agent_id: str
    working_dir: str | Path
    parent_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)
    permissions: set[Permission] = field(default_factory=set)
    resource_limits: Optional[ResourceLimits] = None
    telemetry_config: Optional[TelemetryConfig] = None

class BaseAgent(ABC):
    """Base class for all agents in the system.
    
    This class defines the core interface that all agents must implement.
    It provides basic functionality for:
    - Task management
    - State management
    - Lifecycle management
    - Logging and monitoring
    - Resource management
    - Security and permissions
    - Tool execution
    - Telemetry
    """

    def __init__(
        self,
        name: str,
        context: Optional[AgentContext] = None,
        spec: Optional[dict[str, Any]] = None
    ) -> None:
        """Initialize the base agent.
        
        Args:
            name: Name of the agent
            context: Optional agent context. If not provided, a default context will be created.
            spec: Optional agent specification
        """
        self.name = name
        self.context = context or AgentContext(
            agent_id=name,
            working_dir=Path.cwd(),
        )
        self.spec = spec
        self.status = AgentStatus.INITIALIZED
        self.logger = logging.getLogger(f"agent.{name}")

        # Initialize managers
        self.resource_limits = self.context.resource_limits or ResourceLimits()
        self.permissions = self.context.permissions
        self.telemetry_config = self.context.telemetry_config or TelemetryConfig()

        # Tool management
        self._tools: dict[str, Tool] = {}
        self._registered_tools: set[str] = set()

        # State management
        self._state_file = Path(self.context.working_dir) / f"{name}_state.json"
        self._load_state()

    def register_tool(self, name: str, tool: Tool) -> None:
        """Register a tool with the agent.
        
        Args:
            name: Name of the tool
            tool: Tool instance
        """
        if name in self._tools:
            raise ValueError(f"Tool {name} already registered")
        self._tools[name] = tool
        self._registered_tools.add(name)

    async def execute_tool(self, tool_name: str, args: dict[str, str]) -> ToolResult:
        """Execute a registered tool.
        
        Args:
            tool_name: Name of the tool to execute
            args: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            ValueError: If tool is not registered
            RuntimeError: If tool execution fails
        """
        if tool_name not in self._tools:
            raise ValueError(f"Tool {tool_name} not registered")

        # Check permissions
        required_permission = Permission(resource=tool_name, actions=["execute"])
        if required_permission not in self.permissions:
            raise PermissionError(f"Tool {tool_name} not permitted")

        # Execute within resource limits
        try:
            result = await asyncio.to_thread(
                self._tools[tool_name].execute,
                args,
                self.context.state
            )
            if self.telemetry_config.enabled:
                self.logger.info(f"Tool {tool_name} executed successfully")
            return result
        except Exception as e:
            if self.telemetry_config.enabled:
                self.logger.error(f"Tool {tool_name} failed: {e}")
            raise RuntimeError(f"Tool {tool_name} failed: {e!s}") from e

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the agent.
        
        This method should be called before starting the agent.
        Override this to perform any necessary setup.
        """
        pass

    @abstractmethod
    async def run(self) -> None:
        """Run the agent's main logic.
        
        This is where the core agent functionality should be implemented.
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up any resources used by the agent.
        
        This method will be called when the agent is stopping.
        Override this to perform any necessary cleanup.
        """
        pass

    async def start(self) -> None:
        """Start the agent.
        
        This method handles the full agent lifecycle:
        1. Initialization
        2. Main execution
        3. Cleanup
        """
        try:
            self.status = AgentStatus.RUNNING
            if self.telemetry_config.enabled:
                self.logger.info(f"Starting agent {self.name}")
            await self.initialize()
            await self.run()
            self.status = AgentStatus.COMPLETED
            if self.telemetry_config.enabled:
                self.logger.info(f"Agent {self.name} completed successfully")
        except Exception as e:
            self.status = AgentStatus.FAILED
            if self.telemetry_config.enabled:
                self.logger.error(f"Agent {self.name} failed: {e}", exc_info=True)
            raise
        finally:
            await self.cleanup()
            self._save_state()

    async def stop(self) -> None:
        """Stop the agent.
        
        This will attempt to gracefully stop the agent's execution.
        """
        self.status = AgentStatus.STOPPED
        if self.telemetry_config.enabled:
            self.logger.info(f"Stopping agent {self.name}")
        await self.cleanup()
        self._save_state()

    async def pause(self) -> None:
        """Pause the agent.
        
        This will temporarily suspend the agent's execution.
        """
        if self.status == AgentStatus.RUNNING:
            self.status = AgentStatus.PAUSED
            if self.telemetry_config.enabled:
                self.logger.info(f"Pausing agent {self.name}")
            self._save_state()

    async def resume(self) -> None:
        """Resume the agent.
        
        This will resume a paused agent's execution.
        """
        if self.status == AgentStatus.PAUSED:
            self.status = AgentStatus.RUNNING
            if self.telemetry_config.enabled:
                self.logger.info(f"Resuming agent {self.name}")

    def get_status(self) -> str:
        """Get the current status of the agent."""
        return f"{self.name} is {self.status.value}"

    def update_state(self, key: str, value: Any) -> None:
        """Update the agent's state.
        
        Args:
            key: State key to update
            value: New value for the state
        """
        self.context.state[key] = value
        self._save_state()

    def get_state(self, key: str) -> Any:
        """Get a value from the agent's state.
        
        Args:
            key: State key to retrieve
            
        Returns:
            The value for the given key
        """
        return self.context.state.get(key)

    def _save_state(self) -> None:
        """Save the current state to disk."""
        try:
            with open(self._state_file, "w") as f:
                json.dump(self.context.state, f)
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")

    def _load_state(self) -> None:
        """Load the state from disk if it exists."""
        try:
            if self._state_file.exists():
                with open(self._state_file) as f:
                    self.context.state.update(json.load(f))
        except Exception as e:
            self.logger.error(f"Failed to load state: {e}")

    def __del__(self) -> None:
        """Ensure state is saved when the agent is destroyed."""
        self._save_state()
