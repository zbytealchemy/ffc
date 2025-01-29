# Runtime API Reference

This document provides detailed API documentation for the FFC Runtime components.

## Core Components

### AgentRuntimeEngine

The main engine responsible for executing agent specifications.

```python
class AgentRuntimeEngine:
    def __init__(self, spec: AgentSpec, working_dir: Path):
        """Initialize the runtime engine.

        Args:
            spec: Agent specification dictionary
            working_dir: Working directory for the agent
        """

    def start(self) -> None:
        """Start the runtime engine."""

    def stop(self) -> None:
        """Stop the runtime engine."""

    def register_tool(self, name: str, tool: Any) -> None:
        """Register a tool with the engine."""
```

### AgentSpec

Type definition for agent specifications.

```python
AgentSpec = Dict[str, Any]
"""
{
    "name": str,
    "description": str,
    "tools": List[ToolSpec],
    "permissions": List[Permission],
    "resource_limits": Optional[ResourceLimits]
}
"""
```

### Permission

Defines access permissions for resources.

```python
@dataclass
class Permission:
    resource: str  # Resource pattern (e.g., "data/*")
    actions: List[str]  # Allowed actions (e.g., ["read", "write"])
```

### ResourceLimits

Defines resource constraints for agents.

```python
@dataclass
class ResourceLimits:
    cpu: str  # CPU limit (e.g., "1")
    memory: str  # Memory limit (e.g., "1Gi")
    storage: Optional[str]  # Storage limit
```

## Agent Components

### AgentRunner

Interface for executing agent specifications.

```python
class AgentRunner:
    @classmethod
    async def from_file(cls, spec_path: Path) -> "AgentRunner":
        """Create runner from specification file."""

    async def start(self) -> None:
        """Start the agent runner."""

    async def stop(self) -> None:
        """Stop the agent runner."""

    async def execute_command(self, command: str) -> ToolResult:
        """Execute a command using the runtime engine."""
```

### AgentOrchestrator

Manages distributed agent lifecycles.

```python
class AgentOrchestrator:
    async def deploy_agent(
        self,
        spec: AgentSpec,
        parent_id: Optional[str] = None
    ) -> str:
        """Deploy a new agent."""

    async def terminate_agent(self, agent_id: str) -> None:
        """Terminate an agent."""

    async def get_agent_status(self, agent_id: str) -> AgentStatus:
        """Get agent status."""
```

## Tool System

### ToolSpec

Type definition for tool specifications.

```python
ToolSpec = Dict[str, Any]
"""
{
    "name": str,
    "description": str,
    "class": str,
    "config": Optional[Dict[str, Any]]
}
"""
```

### ToolResult

Type definition for tool execution results.

```python
ToolResult = Dict[str, Any]
"""
{
    "success": bool,
    "result": Any,
    "error": Optional[str]
}
"""
```

## Error Handling

### Exceptions

```python
class AgentError(Exception):
    """Base class for agent-related errors."""

class ToolExecutionError(AgentError):
    """Error during tool execution."""

class PermissionError(AgentError):
    """Permission-related error."""

class ResourceExceededError(AgentError):
    """Resource limit exceeded."""
```

## Usage Examples

### Creating and Running an Agent

```python
# Create agent specification
spec = {
    "name": "data-processor",
    "description": "Processes data files",
    "tools": [
        {
            "name": "process_data",
            "class": "DataProcessingTool",
            "config": {"format": "csv"}
        }
    ],
    "permissions": [
        Permission(resource="data/*", actions=["read"])
    ],
    "resource_limits": ResourceLimits(cpu="1", memory="1Gi")
}

# Create and start agent
runner = AgentRunner(spec)
await runner.start()

# Execute commands
result = await runner.execute_command("process_data")

# Stop agent
await runner.stop()
```

### Managing Distributed Agents

```python
# Initialize orchestrator
orchestrator = AgentOrchestrator(namespace="ffc-agents")

# Deploy agent
agent_id = await orchestrator.deploy_agent(spec)

# Monitor status
status = await orchestrator.get_agent_status(agent_id)

# Terminate when done
await orchestrator.terminate_agent(agent_id)
```
