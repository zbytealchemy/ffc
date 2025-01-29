# Tools API Reference

This document provides detailed API documentation for the FFC Tools system.

## Core Tool System

### BaseTool

Base class for all tools.

```python
class BaseTool:
    async def execute(self, args: Dict[str, Any], state: Any) -> ToolResult:
        """Execute the tool.

        Args:
            args: Tool arguments
            state: Current agent state

        Returns:
            Tool execution result
        """
        raise NotImplementedError
```

### CreateAgentTool

Tool for creating child agents.

```python
class CreateAgentTool:
    def __init__(self, orchestrator: AgentOrchestrator, parent_id: Optional[str]):
        """Initialize the tool.

        Args:
            orchestrator: Agent orchestrator instance
            parent_id: Parent agent ID
        """

    async def execute(
        self,
        args: Dict[str, str],
        state: Any
    ) -> ToolResult:
        """Execute the tool.

        Args:
            args: Must contain 'spec' with agent specification
            state: Current agent state

        Returns:
            Tool execution result with child agent ID
        """
```

## Built-in Tools

### FileSystemTool

Tool for file system operations.

```python
class FileSystemTool(BaseTool):
    """Tool for file system operations."""

    async def execute(
        self,
        args: Dict[str, Any],
        state: Any
    ) -> ToolResult:
        """Execute file system operations.

        Args:
            args: {
                "operation": str,  # read, write, delete
                "path": str,
                "content": Optional[str]
            }
        """
```

### HTTPTool

Tool for making HTTP requests.

```python
class HTTPTool(BaseTool):
    """Tool for making HTTP requests."""

    async def execute(
        self,
        args: Dict[str, Any],
        state: Any
    ) -> ToolResult:
        """Execute HTTP request.

        Args:
            args: {
                "method": str,
                "url": str,
                "headers": Optional[Dict],
                "body": Optional[Any]
            }
        """
```

## Tool Configuration

### ToolConfig

Configuration for tool initialization.

```python
@dataclass
class ToolConfig:
    name: str
    description: str
    permissions: List[Permission]
    config: Optional[Dict[str, Any]] = None
```

### Tool Registration

```python
# Register tool with runtime engine
engine.register_tool(
    name="create_agent",
    tool=CreateAgentTool(orchestrator, agent_id)
)
```

## Tool Development

### Creating Custom Tools

```python
class CustomTool(BaseTool):
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    async def execute(
        self,
        args: Dict[str, Any],
        state: Any
    ) -> ToolResult:
        # Tool implementation
        result = await self._process(args)
        return {
            "success": True,
            "result": result
        }
```

### Tool Permissions

```python
# Define tool permissions
tool_permissions = [
    Permission(
        resource="data/*",
        actions=["read", "write"]
    )
]

# Create tool with permissions
tool_config = ToolConfig(
    name="data_processor",
    description="Processes data files",
    permissions=tool_permissions
)
```

## Error Handling

### Tool-specific Exceptions

```python
class ToolError(Exception):
    """Base class for tool-related errors."""

class ToolConfigError(ToolError):
    """Tool configuration error."""

class ToolExecutionError(ToolError):
    """Tool execution error."""
```

## Usage Examples

### Basic Tool Usage

```python
# Create and configure tool
tool = HTTPTool()

# Execute tool
result = await tool.execute({
    "method": "GET",
    "url": "https://api.example.com/data",
    "headers": {"Authorization": "Bearer token"}
}, state={})

# Handle result
if result["success"]:
    data = result["result"]
else:
    error = result["error"]
```

### Complex Tool Integration

```python
# Create tool chain
tools = [
    FileSystemTool(),
    DataProcessingTool(),
    HTTPTool()
]

# Register tools with engine
for tool in tools:
    engine.register_tool(tool.name, tool)

# Execute tool chain
for tool in tools:
    result = await tool.execute(args, state)
    state = update_state(state, result)
```
