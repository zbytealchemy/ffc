"""Tests for DSL parser."""

import pytest
from ffc.core.parser import ParseError, parse_dsl
from ffc.core.schema import AgentSpec


def test_parse_empty_input():
    """Test parsing empty input."""
    assert parse_dsl("") is None
    assert parse_dsl("  ") is None
    assert parse_dsl("\n") is None


def test_parse_invalid_json():
    """Test parsing invalid JSON."""
    with pytest.raises(ParseError) as exc_info:
        parse_dsl("{invalid json")
    assert "Invalid JSON format" in str(exc_info.value)


def test_parse_invalid_root():
    """Test parsing invalid root element."""
    with pytest.raises(ParseError) as exc_info:
        parse_dsl("[]")
    assert "Input must be a JSON object" in str(exc_info.value)


def test_parse_simple_tool():
    """Test parsing simple tool execution."""
    # Test minimal tool spec
    result = parse_dsl('{"tool": "test_tool"}')
    assert isinstance(result, dict)
    assert result["name"] == "test_tool"
    assert result["config"] == {}

    # Test tool with args
    result = parse_dsl('{"tool": "test_tool", "args": {"key": "value"}}')
    assert isinstance(result, dict)
    assert result["name"] == "test_tool"
    assert result["config"] == {"key": "value"}


def test_parse_invalid_tool():
    """Test parsing invalid tool specification."""
    with pytest.raises(ParseError) as exc_info:
        parse_dsl('{"tool": 123}')
    assert "Field 'tool' must be a string" in str(exc_info.value)

    with pytest.raises(ParseError) as exc_info:
        parse_dsl('{"tool": "test", "args": "invalid"}')
    assert "Field 'args' must be an object" in str(exc_info.value)


def test_parse_agent_spec():
    """Test parsing complete agent specification."""
    spec_json = """{
        "name": "test_agent",
        "description": "Test agent",
        "tasks": [
            {
                "id": "task1",
                "tool": "echo",
                "args": {"message": "hello"}
            }
        ],
        "permissions": [
            {
                "resource": "file_system",
                "actions": ["read", "write"]
            }
        ],
        "resources": {
            "memory_mb": 2048,
            "cpu_cores": 2.0
        },
        "telemetry": {
            "log_level": "DEBUG",
            "trace_enabled": true
        },
        "environment": {
            "DATA_DIR": "/data"
        }
    }"""

    result = parse_dsl(spec_json)
    assert isinstance(result, AgentSpec)
    assert result.name == "test_agent"
    assert result.description == "Test agent"
    assert len(result.tasks) == 1
    assert len(result.permissions) == 1
    assert result.resources.memory_mb == 2048
    assert result.telemetry.log_level == "DEBUG"
    assert result.environment["DATA_DIR"] == "/data"


def test_parse_invalid_agent_spec():
    """Test parsing invalid agent specification."""
    # Missing required field
    with pytest.raises(ParseError) as exc_info:
        parse_dsl('{"name": "test_agent"}')
    assert "tasks" in str(exc_info.value)

    # Invalid task specification
    with pytest.raises(ParseError) as exc_info:
        parse_dsl(
            """{
            "name": "test_agent",
            "tasks": [
                {"id": "task1"}
            ]
        }"""
        )
    assert "tool" in str(exc_info.value)

    # Invalid permission specification
    with pytest.raises(ParseError) as exc_info:
        parse_dsl(
            """{
            "name": "test_agent",
            "tasks": [
                {"id": "task1", "tool": "echo"}
            ],
            "permissions": [
                {"resource": "file_system"}
            ]
        }"""
        )
    assert "actions" in str(exc_info.value)
