# Custom Tools Example

This example shows how to create and use custom tools in the FFC framework.

## Creating a Custom Tool

Here's an example of creating a custom tool for data processing:

```python
from typing import Dict, Any
from ffc.core.tools import BaseTool, ToolResult

class DataProcessingTool(BaseTool):
    """Custom tool for data processing."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.format = config.get("format", "json")

    async def execute(
        self,
        args: Dict[str, Any],
        state: Any
    ) -> ToolResult:
        try:
            # Process data based on format
            data = args.get("data", {})
            if self.format == "json":
                result = self._process_json(data)
            elif self.format == "csv":
                result = self._process_csv(data)
            else:
                raise ValueError(f"Unsupported format: {self.format}")

            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _process_json(self, data: Dict) -> Dict:
        # Add custom JSON processing logic
        return {
            "processed": data,
            "format": "json"
        }

    def _process_csv(self, data: str) -> Dict:
        # Add custom CSV processing logic
        return {
            "processed": data.split(","),
            "format": "csv"
        }
```

## Using the Custom Tool

Here's how to use the custom tool in an agent:

```python
from ffc.agent import AgentRunner

# Define agent specification with custom tool
spec = {
    "name": "data-processor",
    "description": "Processes data using custom tool",
    "tools": [
        {
            "name": "process_data",
            "class": "DataProcessingTool",
            "config": {
                "format": "json"
            }
        }
    ]
}

async def main():
    # Create and start agent
    runner = AgentRunner(spec)
    await runner.start()

    # Process some data
    result = await runner.execute_command(
        "process_data",
        data={"key": "value"}
    )

    print(result)
    await runner.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Tool Development Best Practices

1. **Error Handling**
   - Always return proper ToolResult
   - Include meaningful error messages
   - Handle expected exceptions

2. **Configuration**
   - Use type hints
   - Validate config in __init__
   - Provide sensible defaults

3. **Documentation**
   - Add docstrings
   - Document parameters
   - Include usage examples

4. **Testing**
```python
import pytest
from .tools import DataProcessingTool

@pytest.mark.asyncio
async def test_data_processing_tool():
    tool = DataProcessingTool({"format": "json"})
    result = await tool.execute(
        {"data": {"test": "data"}},
        {}
    )
    assert result["success"]
    assert result["result"]["format"] == "json"
```

## Advanced Features

### 1. State Management
```python
class StatefulTool(BaseTool):
    async def execute(self, args: Dict[str, Any], state: Any) -> ToolResult:
        # Access and modify state
        current_count = state.get("count", 0)
        state["count"] = current_count + 1
        return {"success": True, "result": state["count"]}
```

### 2. Async Operations
```python
class AsyncTool(BaseTool):
    async def execute(self, args: Dict[str, Any], state: Any) -> ToolResult:
        # Perform async operations
        async with aiohttp.ClientSession() as session:
            async with session.get(args["url"]) as response:
                data = await response.json()
                return {"success": True, "result": data}
```

### 3. Resource Management
```python
class ResourceTool(BaseTool):
    async def __aenter__(self):
        # Acquire resources
        self.resource = await acquire_resource()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # Release resources
        await release_resource(self.resource)
```

## Next Steps

- Learn about permissions in the [Architecture Overview](../architecture/overview.md#security-model)
- Explore [LLM Integration](../guides/llm-integration.md)
- See [Agent Orchestration](../guides/agent-orchestration.md)
