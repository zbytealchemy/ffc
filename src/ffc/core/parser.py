"""DSL parser for agent specifications."""

import json
import re
from dataclasses import dataclass
from typing import Any

from .schema import AgentSpec, validate_dsl
from .types import ToolSpec


@dataclass
class ParseError(Exception):
    """Base class for parsing errors."""

    message: str
    line: int
    column: int

    def __str__(self) -> str:
        return f"Error at line {self.line}, column {self.column}: {self.message}"


def parse_dsl(text: str) -> ToolSpec | AgentSpec | None:
    """Parse a DSL command or specification.

    Supports three formats:
    1. Simple text command:
    read_file file_path="/path/to/file.txt"

    2. Simple tool execution:
    {
        "tool": "tool_name",
        "args": {
            "arg1": "value1",
            "arg2": "value2"
        }
    }

    3. Complete agent specification:
    {
        "version": "1.0",
        "name": "my_agent",
        "description": "My agent description",
        "permissions": [...],
        "tasks": [...],
        "resources": {...},
        "telemetry": {...},
        "environment": {...},
        "metadata": {...}
    }

    Args:
        text: DSL text to parse

    Returns:
        ToolSpec for simple commands, AgentSpec for full specifications,
        or None if text is empty

    Raises:
        ParseError: If the text is invalid JSON or missing required fields
    """
    if not text.strip():
        return None

    # First try to parse as JSON
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ParseError("Input must be a JSON object", 1, 1)

        # Check if this is a simple tool execution
        if "tool" in data:
            return _parse_tool_spec(data)

        # Otherwise, try to parse as full agent specification
        try:
            return validate_dsl(data)
        except ValueError as e:
            raise ParseError(str(e), 1, 1) from e

    except json.JSONDecodeError as e:
        # If not valid JSON, try to parse as text command
        try:
            return _parse_text_command(text)
        except ParseError:
            # If both JSON and text command parsing fail, raise JSON error
            raise ParseError("Invalid JSON format", e.lineno, e.colno) from e


def _parse_text_command(text: str) -> ToolSpec:
    """Parse a plain text command.

    Args:
        text: Command text to parse

    Returns:
        ToolSpec instance

    Raises:
        ParseError: If the command is invalid
    """
    # Split into tool name and args
    parts = text.strip().split(maxsplit=1)
    if not parts:
        raise ParseError("Empty command", 1, 1)

    tool_name = parts[0]
    args_text = parts[1] if len(parts) > 1 else ""

    # Parse args of form key="value" or key=value
    args = {}
    if args_text:
        arg_pattern = r'(\w+)=(?:"([^"]*)"|\b(\S+)\b)'
        matches = list(re.finditer(arg_pattern, args_text))
        if not matches:
            raise ParseError("Invalid command format. Expected key=value pairs", 1, 1)

        for match in matches:
            key = match.group(1)
            # Group 2 is quoted value, group 3 is unquoted value
            value = match.group(2) if match.group(2) is not None else match.group(3)
            args[key] = value

    return ToolSpec(name=tool_name, config=args, clazz=None)


def _parse_tool_spec(data: dict[str, Any]) -> ToolSpec:
    """Parse a simple tool execution specification.

    Args:
        data: Tool specification data

    Returns:
        ToolSpec instance

    Raises:
        ParseError: If the specification is invalid
    """
    if not isinstance(data["tool"], str):
        raise ParseError("Field 'tool' must be a string", 1, 1)

    if "args" in data and not isinstance(data["args"], dict):
        raise ParseError("Field 'args' must be an object", 1, 1)

    return ToolSpec(name=data["tool"], config=data.get("args", {}), clazz=None)
