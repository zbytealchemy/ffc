# Installation Guide

## System Requirements

- Python 3.8 or higher
- Poetry for dependency management
- Docker (optional)
- Git

## Installation Steps

### 1. Install Poetry

If you haven't installed Poetry yet:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 2. Clone the Repository

```bash
git clone https://github.com/zbytealchemy/ffc.git
cd ffc
```

### 3. Install Dependencies

```bash
# Install all components
make install
```

### 4. Verify Installation

```bash
# Run tests
make test

# Run linting
make lint
```

## Docker Installation

If you prefer using Docker:

```bash
# Build development image
make docker-dev-build

# Run in container
make docker-dev-run
```

## Development Setup

For development work:

```bash
# Setup development environment
make setup-dev

# This will:
# 1. Install poetry
# 2. Install pre-commit hooks
# 3. Setup git hooks
# 4. Install all dependencies
```

## Troubleshooting

If you encounter any issues:

1. Make sure you have the correct Python version
2. Update Poetry to the latest version
3. Clear Poetry cache if needed
4. Check the logs in the `logs` directory

## Next Steps

- Follow the [Getting Started Guide](getting-started.md)
- Read about [Architecture](../architecture/overview.md)
- Try the [Basic Agent Example](../examples/basic-agent.md)
