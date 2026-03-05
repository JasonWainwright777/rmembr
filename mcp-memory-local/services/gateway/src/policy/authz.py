"""ToolAuthz: per-tool authorization enforcement."""

from .types import ToolPolicy


class AuthorizationError(Exception):
    """Raised when a tool call is denied by policy."""

    def __init__(self, tool_name: str, role: str):
        self.tool_name = tool_name
        self.role = role
        super().__init__(f"Unauthorized: tool '{tool_name}' requires a role with access (current: '{role}')")


class ToolAuthz:
    """Per-tool authorization enforcement."""

    def __init__(self, policy: ToolPolicy):
        self.policy = policy
        self._role_tools: dict[str, set[str]] = {
            role: set(tools) for role, tools in policy.roles.items()
        }

    def authorize(self, tool_name: str, role: str | None = None) -> bool:
        """Check if the given role is authorized to call the tool.

        Returns True if authorized, False if denied.
        Uses default_role when role is None.
        """
        effective_role = role or self.policy.default_role
        allowed = self._role_tools.get(effective_role, set())
        if tool_name in allowed:
            return True
        if self.policy.default_action == "allow":
            return True
        return False

    def enforce(self, tool_name: str, role: str | None = None) -> None:
        """Enforce authorization, raising AuthorizationError if denied."""
        effective_role = role or self.policy.default_role
        if not self.authorize(tool_name, effective_role):
            raise AuthorizationError(tool_name, effective_role)
