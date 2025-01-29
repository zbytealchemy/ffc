# Docker Deployment Guide

This guide covers deploying FFC agents using Docker and Kubernetes.

## Docker Configuration

### Base Image
FFC uses a multi-stage build process with optimized base images:
- Build stage: `python:3.10-slim`
- Runtime stage: `gcr.io/distroless/python3:nonroot`

### Container Structure

```dockerfile
# Build Stage
FROM python:3.10-slim as builder
COPY poetry.lock pyproject.toml ./
RUN pip install poetry && \
    poetry config virtualenvs.in-project true && \
    poetry install --no-root

# Runtime Stage
FROM gcr.io/distroless/python3:nonroot
COPY --from=builder .venv .venv
COPY . .
```

## Resource Configuration

### Memory Management
- Container memory limits are configurable
- Default limits are set in deployment specs
- Runtime memory monitoring is enabled

### CPU Allocation
- CPU requests and limits are configurable
- Default CPU shares are set for fair scheduling
- CPU usage monitoring is enabled

## Health Checks

### HTTP Health Endpoint
- Available at `/health`
- Returns system metrics and status
- Configurable check intervals

### Docker Health Check
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1
```

## Environment Setup

### Configuration Management
- Environment variables for runtime configuration
- Secret management through Kubernetes
- Volume management for persistent storage

## Deployment Commands

### Basic Deployment
```bash
docker run -d \
  --name ffc-agent \
  -p 8080:8080 \
  -v /path/to/logs:/app/logs \
  ghcr.io/ffc/agent-runtime:latest
```

### Management Commands
```bash
# View logs
docker logs ffc-agent

# Stop container
docker stop ffc-agent

# Start container
docker start ffc-agent

# Remove container
docker rm -f ffc-agent
```

## Security Considerations

### Container Security
- Non-root user execution
- Minimal base image
- No unnecessary packages
- Regular security updates

### Network Security
- Exposed ports are configurable
- Internal communication over secure channels
- Support for network policies

## Monitoring and Logging

### Log Configuration
- JSON-formatted logging
- Log rotation enabled
- Volume mounting for persistence

### Metrics
- Container metrics available
- Resource usage tracking
- Health check status monitoring
