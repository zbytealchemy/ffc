# Python runtime Makefile

.PHONY: install format lint test clean docker-build docker-run docker-stop docker-logs help ci-validate format-tabs docker-dev-build docker-dev-run docker-dev-debug docker-dev-shell docs docs-serve setup-dev

# Poetry path
POETRY := poetry

# Define the project root variable
PROJECT_ROOT := .

PROJECT_SRC := src

# Python source directories
PYTHON_DIRS := src tests

# Docker image configuration
DOCKER_REGISTRY := ghcr.io/ffc
DOCKER_IMAGE := agent-runtime
DOCKER_TAG := latest
CONTAINER_NAME := ffc-runtime

# Docker resource limits
MEMORY_LIMIT := 512m
CPU_LIMIT := 1.0

# Poetry installation command
POETRY_INSTALLER := curl -sSL https://install.python-poetry.org

# Install dependencies
install:
	poetry install --no-interaction --no-ansi
	$(POETRY) install || ($(POETRY) lock && $(POETRY) install)

# Lock dependencies
lock:
	$(POETRY) lock

# Format code
format:
	$(POETRY) run ruff format $(PYTHON_DIRS)
	$(POETRY) run ruff check --fix --unsafe-fixes $(PYTHON_DIRS)

# Fix tab/space indentation issues
format-tabs:
	$(POETRY) run autopep8 --in-place --recursive --select=E101,W191 $(PYTHON_DIRS)

# Lint code
lint:
	$(POETRY) run ruff check $(PYTHON_DIRS)

# Run tests
test:
	$(POETRY) run pytest tests/ -v

docs:  ## Build documentation
	poetry install --with docs
	poetry run mkdocs build

docs-serve:  ## Serve documentation locally
	poetry run mkdocs serve

# Run tests with coverage
test-coverage:
	$(POETRY) run pytest tests/ -v --cov=ffc --cov-report=xml --cov-report=term-missing

# CI validation
ci-validate: lint test-coverage

# Clean python cache files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type f -name "coverage.xml" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +

# Docker commands
docker-build:
	docker build -t $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):$(DOCKER_TAG) -f Dockerfile .
	docker tag $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):$(DOCKER_TAG) $(DOCKER_IMAGE):local

docker-run:
	docker run --rm -d \
		--name $(CONTAINER_NAME) \
		-p 8080:8080 \
		--memory=$(MEMORY_LIMIT) \
		--cpus=$(CPU_LIMIT) \
		--memory-swap=$(MEMORY_LIMIT) \
		--pids-limit=100 \
		--security-opt=no-new-privileges \
		$(DOCKER_IMAGE):local

docker-stop:
	-docker stop $(CONTAINER_NAME)
	-docker rm $(CONTAINER_NAME)

docker-logs:
	docker logs -f $(CONTAINER_NAME)

docker-push:
	docker push $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):$(DOCKER_TAG)

docker-test: docker-build docker-run
	@echo "Waiting for container to start..."
	@sleep 5
	@curl -s http://localhost:8080/health
	@echo "\nContainer is healthy!"
	@make docker-stop

# Development commands
docker-dev-build:
	cd $(PWD) && docker build -t ffc-framework-dev -f Dockerfile.dev .

docker-dev-run: docker-dev-build
	docker run --rm \
		-p 8080:8080 \
		-v $(PWD):/app \
		-v ffc-framework-logs:/app/logs \
		--name ffc-framework-dev \
		ffc-framework-dev

docker-dev-debug: docker-dev-build
	docker run --rm -it \
		-p 8080:8080 \
		-p 5678:5678 \
		-v $(PWD):/app \
		-v ffc-framework-logs:/app/logs \
		-e ENABLE_DEBUGGER=true \
		--name ffc-framework-dev \
		ffc-framework-dev

docker-dev-shell: docker-dev-build
	docker run --rm -it \
		-v $(PWD):/app \
		-v ffc-framework-logs:/app/logs \
		--name ffc-framework-dev \
		--entrypoint /bin/bash \
		ffc-framework-dev

# New setup-dev target
setup-dev: ## Setup development environment
	@echo "🔧 Setting up development environment..."
	@echo "\n📦 Installing Poetry..."
	$(POETRY_INSTALLER) | python3 -
	@echo "\n📚 Installing project dependencies..."
	$(POETRY) install
	@echo "\n🔍 Installing pre-commit hooks..."
	$(POETRY) run pre-commit install
	@echo "\n🎯 Setting up git hooks..."
	git config core.hooksPath .github/hooks
	@echo "\n✨ Development environment setup complete!"
	@echo "Run 'make help' to see available commands"

# Show help
help:
	@echo "Python Runtime Build System"
	@echo ""
	@echo "Available commands:"
	@echo "  make setup-dev     - Setup complete development environment"
	@echo "  make install       - Install dependencies using poetry"
	@echo "  make format        - Format code using ruff"
	@echo "  make lint          - Run all linters (ruff)"
	@echo "  make test          - Run tests"
	@echo "  make test-coverage - Run tests with coverage"
	@echo "  make clean         - Clean up python cache files"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run    - Run Docker container"
	@echo "  make docker-stop   - Stop and remove Docker container"
	@echo "  make docker-logs   - View container logs"
	@echo "  make docker-test   - Build, run, test, and cleanup container"
	@echo "  make docker-push   - Push Docker image to registry"
	@echo "  make ci-validate   - Run CI validation steps"
	@echo "  make docker-dev-build  - Build Docker image for development"
	@echo "  make docker-dev-run    - Run Docker container for development"
	@echo "  make docker-dev-debug  - Run Docker container for development with debugger"
	@echo "  make docker-dev-shell  - Run Docker container for development with shell"
