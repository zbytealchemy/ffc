# Build stage
FROM python:3.10-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean autoclean \
    && apt-get autoremove --yes

# Install poetry
ENV POETRY_VERSION=1.6.1
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VENV=/opt/poetry-venv
ENV POETRY_CACHE_DIR=/opt/.cache

# Configure poetry
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV POETRY_NO_INTERACTION=1

# Install poetry separated from system interpreter
RUN python3 -m venv $POETRY_VENV \
    && $POETRY_VENV/bin/pip install -U pip "setuptools>=70.0.0" \
    && $POETRY_VENV/bin/pip install poetry==${POETRY_VERSION} \
    && rm -rf $POETRY_CACHE_DIR/*

# Add `poetry` to PATH
ENV PATH="${POETRY_VENV}/bin:${PATH}"

# Ensure base image has updated setuptools
RUN pip install --no-cache-dir "setuptools>=70.0.0"

WORKDIR /app

# Copy only dependency files first
COPY pyproject.toml ./ 
COPY poetry.lock ./ 

# Install dependencies first (this layer will be cached)
RUN poetry install --only main --no-interaction --no-ansi --no-root \
    && rm -rf $POETRY_CACHE_DIR/*

# Add README.md
COPY ../README.md ./

# Copy the rest of the application code
COPY src/ ./src
COPY tests/ ./tests

# Install the project itself
RUN poetry install --only main --no-interaction --no-ansi \
    && rm -rf $POETRY_CACHE_DIR/*

# Create and set permissions for log directory
RUN mkdir -p /app/logs && \
    chown -R nobody:nogroup /app/logs

# Clean up Python cache files
RUN find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /app -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# Runtime stage
FROM python:3.10-slim AS runtime

# Update setuptools in runtime stage
RUN pip install --no-cache-dir "setuptools>=70.0.0"

# Create non-root user
RUN groupadd -r nonroot && useradd -r -g nonroot nonroot

# Install curl for health check
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean autoclean \
    && apt-get autoremove --yes

# Set working directory
WORKDIR /app

# Copy log directory with correct permissions
COPY --from=builder --chown=nonroot:nonroot /app/logs /app/logs

# Copy only the necessary files from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src/ ./src

# Set Python path and environment variables
ENV PYTHONPATH=/app
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Configure logging
ENV FFC_LOG_LEVEL=INFO
ENV FFC_LOG_FILE=/app/logs/ffc.log
ENV FFC_LOG_MAX_BYTES=10485760
ENV FFC_LOG_BACKUP_COUNT=5

# Security hardening
ENV PYTHON_HARDEN=1
ENV PYTHONWARNINGS="ignore:Unverified HTTPS request"

# Resource limits (these will be enforced by Docker)
ENV MEMORY_LIMIT="512M"
ENV CPU_LIMIT="1.0"

# Run as non-root user
USER nonroot

# Configure health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

# Command to run the application
CMD ["/app/.venv/bin/python3", "-m", "ffc"]
