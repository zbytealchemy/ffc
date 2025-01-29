# Basic Agent Example

This example demonstrates how to create and run a basic FFC agent.

## Simple File Processing Agent

Here's a complete example of an agent that processes files:

```python
from ffc.agent import AgentRunner
from pathlib import Path

# Define agent specification
spec = {
    "name": "file-processor",
    "description": "Processes text files and counts words",
    "tools": [
        {
            "name": "read_file",
            "class": "FileSystemTool",
            "config": {
                "operation": "read"
            }
        },
        {
            "name": "write_file",
            "class": "FileSystemTool",
            "config": {
                "operation": "write"
            }
        }
    ],
    "permissions": [
        {
            "resource": "data/*",
            "actions": ["read", "write"]
        }
    ]
}

async def main():
    # Create runner
    runner = AgentRunner(spec)

    # Start agent
    await runner.start()

    # Process file
    result = await runner.execute_command(
        "read_file",
        path="data/input.txt"
    )

    if result["success"]:
        # Count words
        words = len(result["content"].split())

        # Write results
        await runner.execute_command(
            "write_file",
            path="data/output.txt",
            content=f"Word count: {words}"
        )

    # Stop agent
    await runner.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Running the Example

1. Save the code as `file_processor.py`

2. Create input file:
```bash
echo "Hello Firefly Catcher Framework!" > data/input.txt
```

3. Run the agent:
```bash
python file_processor.py
```

4. Check the output:
```bash
cat data/output.txt
# Should show: Word count: 4
```

## Key Concepts Demonstrated

- Agent specification structure
- Tool configuration
- Permission setup
- Agent lifecycle management
- Command execution
- Error handling

## Next Steps

- Try the [Custom Tools Example](custom-tools.md)
- Learn about [Agent Orchestration](../guides/agent-orchestration.md)
- Explore [LLM Integration](../guides/llm-integration.md)
