"""Common type definitions for the agent runtime."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, TypedDict


class AgentStatus(Enum):
    """Status states for an agent."""
    PENDING = "pending"      # Initial state when agent is being created
    INITIALIZED = "initialized"  # Agent is initialized but not yet running
    RUNNING = "running"      # Agent is actively executing
    PAUSED = "paused"       # Agent execution is temporarily suspended
    COMPLETED = "completed"  # Agent has finished successfully
    FAILED = "failed"       # Agent encountered an error
    TERMINATED = "terminated"  # Agent was explicitly stopped


class Tool(Protocol):
    """Protocol defining the interface for tools."""
    def execute(
        self,
        args: dict[str, str],
        state: Any,
    ) -> "ToolResult":
        """Execute the tool with given arguments and state.
        
        Args:
            args: Tool arguments
            state: Current agent state
            
        Returns:
            Tool execution results
        """
        ...


class ToolSpec(TypedDict):
    """Type definition for tool specification."""
    name: str
    config: dict[str, Any]
    clazz: Any  # Tool implementation class


class AgentSpec(TypedDict, total=False):
    """Type definition for agent specification."""
    tools: list[ToolSpec]


@dataclass
class AgentState:
    """Agent state definition."""
    memory: dict[str, str]
    context: dict[str, str]
    state: AgentStatus
    working_dir: Path | None
    permissions: Any | None
    resources: Any | None
    telemetry: Any | None


class ToolResult(TypedDict):
    """Type definition for tool execution results."""
    status: str
    data: dict[str, Any]
    metadata: dict[str, Any]
