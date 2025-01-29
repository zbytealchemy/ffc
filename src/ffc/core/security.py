"""Security components for the FFC Framework."""

from dataclasses import dataclass

from .schema import Permission


@dataclass
class SecurityError(Exception):
    """Base class for security-related errors."""

    message: str
    permission: str | None = None

    def __str__(self) -> str:
        if self.permission:
            return f"Security error for permission '{self.permission}': {self.message}"
        return f"Security error: {self.message}"


class SandboxContext:
    """Context manager for sandbox operations."""

    def __init__(self, manager: "SandboxManager", resource: str, action: str):
        self.manager = manager
        self.resource = resource
        self.action = action

    def __enter__(self):
        self.manager.check_permission(self.resource, self.action)
        if self.resource not in self.manager._active_contexts:
            self.manager._active_contexts[self.resource] = []
        self.manager._active_contexts[self.resource].append(self.action)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.resource in self.manager._active_contexts:
            if self.action in self.manager._active_contexts[self.resource]:
                self.manager._active_contexts[self.resource].remove(self.action)
            if not self.manager._active_contexts[self.resource]:
                del self.manager._active_contexts[self.resource]
        return False


class SandboxManager:
    """Manages security sandbox for tool execution."""

    def __init__(self, permissions: list[Permission]) -> None:
        """Initialize sandbox manager.

        Args:
            permissions: List of allowed permissions
        """
        self.permissions = {p.resource: p for p in permissions}
        self._active_contexts: dict[str, list[str]] = {}

    def check_permission(self, resource: str, action: str) -> None:
        """Check if an action is allowed for a resource.

        Args:
            resource: Resource identifier
            action: Action to check

        Raises:
            SecurityError: If the action is not allowed
        """
        if resource not in self.permissions:
            raise SecurityError(f"Access to resource '{resource}' is not allowed")

        permission = self.permissions[resource]
        if action not in permission.actions:
            raise SecurityError(
                f"Action '{action}' is not allowed for resource '{resource}'",
                resource,
            )

        # Check conditions if any
        if permission.conditions:
            self._check_conditions(permission)

    def _check_conditions(self, permission: Permission) -> None:
        """Check if permission conditions are met.

        Args:
            permission: Permission to check

        Raises:
            SecurityError: If conditions are not met
        """
        if not permission.conditions:
            return

        # TODO: Implement condition checking based on context
        # This could include things like:
        # - Time-based conditions (only during business hours)
        # - Rate limiting
        # - Resource quotas
        # - Network restrictions
        pass

    def sandbox_context(self, resource: str, action: str) -> "SandboxContext":
        """Create a sandboxed context for executing an action.

        Args:
            resource: Resource identifier
            action: Action to perform

        Returns:
            SandboxContext instance
        """
        return SandboxContext(self, resource, action)
