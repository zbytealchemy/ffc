"""Base tool implementation and utilities."""

import shutil
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Protocol

from .resources import ResourceTracker
from .schema import Permission, ResourceLimits, TelemetryConfig
from .security import SandboxManager
from .telemetry import TelemetryManager
from .types import AgentState, ToolResult


class Tool(Protocol):
    """Protocol defining the interface for tools."""

    def execute(self, args: dict[str, str], state: AgentState) -> ToolResult:
        """Execute the tool with given arguments and state.

        Args:
            args: Tool arguments
            state: Current agent state

        Returns:
            Tool execution results
        """
        ...


class BaseTool(ABC):
    """Base class for tool implementations."""

    def __init__(
        self,
        config: dict[str, Any],
        permissions: list[Permission] | None = None,
        resource_limits: ResourceLimits | None = None,
        telemetry_config: TelemetryConfig | None = None,
    ) -> None:
        """Initialize the tool.

        Args:
            config: Tool configuration
            permissions: Tool permissions
            resource_limits: Resource limits
            telemetry_config: Telemetry configuration
        """
        self.config = config
        self._sandbox = SandboxManager(permissions or [])
        self._resource_tracker = ResourceTracker(resource_limits)
        self._telemetry = TelemetryManager(telemetry_config)

    def execute(self, args: dict[str, str], state: AgentState) -> ToolResult:
        """Execute the tool with given arguments and state.

        Args:
            args: Tool arguments
            state: Current agent state

        Returns:
            Tool execution results
        """
        start_time = time.time()
        start_resources = self._resource_tracker.get_usage()

        try:
            # Create sandbox context for tool execution
            tool_name = self.config.get("name")
            if not tool_name:
                raise ValueError("Tool config must include 'name' field")

            with self._sandbox.sandbox_context(tool_name, "execute"):
                result = self._execute_impl(args, state)
                if not isinstance(result, dict):
                    raise RuntimeError("Tool must return a dictionary")
                if not all(k in result for k in ["status", "data", "metadata"]):
                    raise RuntimeError(
                        "Tool result must have status, data, and metadata fields"
                    )

            end_time = time.time()
            end_resources = self._resource_tracker.get_usage()

            execution_time = end_time - start_time
            memory_used = end_resources.get("memory_mb", 0) - start_resources.get(
                "memory_mb", 0
            )
            cpu_cores = end_resources.get("cpu_cores", 0) - start_resources.get(
                "cpu_cores", 0
            )

            self._telemetry.emit_event(
                "tool_complete",
                {
                    "tool": self.__class__.__name__,
                    "result": result,
                    "resources": {
                        "memory_mb": memory_used,
                        "cpu_cores": cpu_cores,
                        "execution_time": execution_time,
                    },
                },
                source="tool",
            )

            return result
        except Exception as e:
            end_time = time.time()
            end_resources = self._resource_tracker.get_usage()

            execution_time = end_time - start_time
            memory_used = end_resources.get("memory_mb", 0) - start_resources.get(
                "memory_mb", 0
            )
            cpu_cores = end_resources.get("cpu_cores", 0) - start_resources.get(
                "cpu_cores", 0
            )

            self._telemetry.emit_event(
                "tool_error",
                {
                    "tool": self.__class__.__name__,
                    "error": str(e),
                    "resources": {
                        "memory_mb": memory_used,
                        "cpu_cores": cpu_cores,
                        "execution_time": execution_time,
                    },
                },
                source="tool",
            )

            raise

    @abstractmethod
    def _validate_inputs(self, args: dict[str, str]) -> None:
        """Validate tool inputs.

        Args:
            args: Tool arguments to validate

        Raises:
            ValueError: If validation fails
        """
        pass

    @abstractmethod
    def _execute_impl(self, args: dict[str, str], state: AgentState) -> ToolResult:
        """Implement the tool's core functionality.

        Args:
            args: Tool arguments
            state: Current agent state

        Returns:
            Tool execution results
        """
        pass


# File Processing Tools


class FileReaderTool:
    """Tool for reading files."""

    def __init__(self, config: Dict[str, Any], **kwargs):
        """Initialize the tool.

        Args:
            config: Tool configuration
            **kwargs: Additional configuration
        """
        self.supported_extensions = config.get("supported_extensions", [])

    def execute(self, args: Dict[str, str], state: AgentState) -> ToolResult:
        """Execute the tool.

        Args:
            args: Tool arguments containing file path
            state: Current agent state

        Returns:
            Tool execution result containing file contents
        """
        file_path = Path(args["file_path"])
        if not file_path.exists():
            return {
                "status": "error",
                "data": {"error": f"File not found: {file_path}"},
                "metadata": {"tool": "file_reader"},
            }

        if (
            self.supported_extensions
            and file_path.suffix not in self.supported_extensions
        ):
            return {
                "status": "error",
                "data": {"error": f"Unsupported file extension: {file_path.suffix}"},
                "metadata": {"tool": "file_reader"},
            }

        try:
            content = file_path.read_text()
            return {
                "status": "success",
                "data": {"content": content},
                "metadata": {"tool": "file_reader"},
            }
        except Exception as e:
            return {
                "status": "error",
                "data": {"error": f"Error reading file: {e!s}"},
                "metadata": {"tool": "file_reader"},
            }


class FileWriterTool:
    """Tool for writing files."""

    def __init__(self, config: Dict[str, Any], **kwargs):
        """Initialize the tool.

        Args:
            config: Tool configuration
            **kwargs: Additional configuration
        """
        pass

    def execute(self, args: Dict[str, str], state: AgentState) -> ToolResult:
        """Execute the tool.

        Args:
            args: Tool arguments containing file path and content
            state: Current agent state

        Returns:
            Tool execution result
        """
        file_path = Path(args["file_path"])
        content = args["content"]

        try:
            # Create directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content to file
            file_path.write_text(content)

            return {
                "status": "success",
                "data": {"file_path": str(file_path)},
                "metadata": {"tool": "file_writer"},
            }
        except Exception as e:
            return {
                "status": "error",
                "data": {"error": f"Error writing file: {e!s}"},
                "metadata": {"tool": "file_writer"},
            }


class FileMoverTool:
    """Tool for moving files."""

    def __init__(self, config: Dict[str, Any], **kwargs):
        """Initialize the tool.

        Args:
            config: Tool configuration
            **kwargs: Additional configuration
        """
        pass

    def execute(self, args: Dict[str, str], state: AgentState) -> ToolResult:
        """Execute the tool.

        Args:
            args: Tool arguments containing source and destination paths
            state: Current agent state

        Returns:
            Tool execution result
        """
        src_path = Path(args["source"])
        dst_path = Path(args["destination"])

        if not src_path.exists():
            return {
                "status": "error",
                "data": {"error": f"Source file not found: {src_path}"},
                "metadata": {"tool": "file_mover"},
            }

        try:
            # Create destination directory if it doesn't exist
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            # Move the file
            shutil.move(str(src_path), str(dst_path))

            return {
                "status": "success",
                "data": {"source": str(src_path), "destination": str(dst_path)},
                "metadata": {"tool": "file_mover"},
            }
        except Exception as e:
            return {
                "status": "error",
                "data": {"error": f"Error moving file: {e!s}"},
                "metadata": {"tool": "file_mover"},
            }
