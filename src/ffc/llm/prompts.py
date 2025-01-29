"""Prompt management system for LLM interactions."""

import json
from dataclasses import dataclass, field
from string import Template
from typing import Any

import jsonschema
from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    Undefined,
    nodes,
    select_autoescape,
)


@dataclass
class PromptTemplate:
    """Template for generating prompts."""

    name: str
    template: str
    variables: set[str] = field(default_factory=set)
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    variable_schemas: dict[str, dict] = field(default_factory=dict)

    def __post_init__(self):
        """Extract variables from template if not provided."""
        if not self.variables:
            self.variables = set()

            template = Template(self.template)
            self.variables.update(
                name
                for _, name, _, _ in template.pattern.findall(template.template)
                if name  # Skip empty strings
            )

            env = Environment(autoescape=select_autoescape())
            ast = env.parse(self.template)
            self.variables.update(
                node.name
                for node in ast.find_all(nodes.Name)
                if hasattr(node, "name") and node.name  # Skip empty strings
            )


class PromptRenderer:
    """Abstract base class for prompt renderers."""

    def render(self, template: PromptTemplate, variables: dict[str, Any]) -> str:
        """Render prompt template with variables.

        Args:
            template: Prompt template to render
            variables: Variables to use in rendering

        Returns:
            Rendered prompt string
        """
        raise NotImplementedError("Subclasses must implement render()")


class SimpleRenderer(PromptRenderer):
    """Simple string template renderer."""

    def render(self, template: PromptTemplate, variables: dict[str, Any]) -> str:
        """Render a template with variables."""
        return Template(template.template).safe_substitute(variables)


class JinjaRenderer(PromptRenderer):
    """Jinja2 template renderer."""

    def __init__(
        self, template_dirs: list[str] | None = None, strict_undefined: bool = True
    ):
        """Initialize renderer with custom environment."""
        self.env = Environment(
            loader=FileSystemLoader(template_dirs) if template_dirs else None,
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined if strict_undefined else Undefined,
        )
        self.env.filters["tojson"] = json.dumps

    def render(self, template: PromptTemplate, variables: dict[str, Any]) -> str:
        """Render a template with variables."""
        jinja_template = self.env.from_string(template.template)
        return jinja_template.render(**variables)


@dataclass
class ResponseSchema:
    """Schema for validating LLM responses."""

    format: str
    required_fields: set[str]
    schema: dict[str, Any]

    def validate(self, response: str) -> tuple[bool, str | None]:
        """Validate a response against the schema."""
        try:
            if self.format == "json":
                data = json.loads(response)

                # Check required fields first
                missing_fields = self.required_fields - set(data.keys())
                if missing_fields:
                    return False, f"Missing required fields: {missing_fields}"

                # Then validate against JSON schema
                try:
                    jsonschema.validate(data, self.schema)
                except jsonschema.ValidationError as err:
                    return False, str(err)

                return True, None
            else:
                return False, f"Unsupported format: {self.format}"
        except json.JSONDecodeError:
            return False, "Invalid JSON"


class PromptManager:
    """Manager for prompt templates."""

    def __init__(
        self,
        renderer: SimpleRenderer | JinjaRenderer | None = None,
        template_dirs: list[str] | None = None,
    ):
        """Initialize with a renderer."""
        self.templates: dict[str, PromptTemplate] = {}
        self.renderer = renderer or JinjaRenderer(template_dirs)

    def add_template(self, template: PromptTemplate):
        """Add a template to the manager."""
        self.templates[template.name] = template

    def get_template(self, name: str) -> PromptTemplate:
        """Get a template by name."""
        if name not in self.templates:
            raise KeyError(f"Template not found: {name}")
        return self.templates[name]

    def render(self, name: str, variables: dict[str, Any]) -> str:
        """Render a template by name with variables."""
        template = self.get_template(name)

        # Validate variables
        missing_vars = template.variables - set(variables.keys())
        if missing_vars:
            raise ValueError(f"Missing variables: {missing_vars}")

        # Validate variable schemas
        for var, schema in template.variable_schemas.items():
            if var in variables:
                try:
                    jsonschema.validate(variables[var], schema)
                except jsonschema.ValidationError as e:
                    raise ValueError(f"Invalid variable {var}: {e}") from e

        return self.renderer.render(template, variables)
