# Getting Started

This guide will help you get started with the Firefly Catcher Framework.

## Prerequisites

- Python 3.8 or higher
- Poetry for dependency management
- Docker (optional, for containerized deployment)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/zbytealchemy/ffc.git
cd ffc
```

2. Install dependencies:
```bash
make install
```

## Quick Start

1. Create your first agent specification:
```yaml
name: hello-world
description: "A simple hello world agent"
tools:
  - name: print
    class: PrintTool
```

2. Run the agent:
```python
from ffc.agent import AgentRunner
from pathlib import Path

runner = await AgentRunner.from_file(Path("agent_spec.yaml"))
await runner.start()
```

## Next Steps

- Check out the [Architecture Overview](../architecture/overview.md)
- Learn about [Agent Orchestration](agent-orchestration.md)
- Explore [Custom Tools](../examples/custom-tools.md)
