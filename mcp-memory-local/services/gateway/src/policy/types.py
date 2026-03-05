"""Policy DTOs: PolicyBundle, PersonaPolicy, ToolPolicy, BudgetPolicy."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PersonaPolicy:
    """Persona -> allowed classification levels."""
    allowed_classifications: dict[str, list[str]]
    # e.g. {"human": ["public", "internal"], "external": ["public"]}


@dataclass(frozen=True)
class ToolPolicy:
    """Per-tool authorization rules."""
    default_action: str  # "deny" or "allow"
    roles: dict[str, list[str]]  # role_name -> list of allowed tool names
    default_role: str  # role assigned when no explicit role claim


@dataclass(frozen=True)
class BudgetPolicy:
    """Request budget controls."""
    max_bundle_chars: int = 40000
    max_sources: int = 50
    default_k: int = 12
    tool_timeouts: dict[str, int] = field(default_factory=dict)
    cache_ttl_seconds: int = 300


@dataclass(frozen=True)
class PolicyBundle:
    """Complete policy configuration."""
    version: str
    persona: PersonaPolicy
    tool_auth: ToolPolicy
    budgets: BudgetPolicy

    @classmethod
    def from_dict(cls, d: dict) -> "PolicyBundle":
        """Parse from JSON dict."""
        persona = PersonaPolicy(
            allowed_classifications=d.get("persona_classification", {
                "human": ["public", "internal"],
                "agent": ["public", "internal"],
                "external": ["public"],
            })
        )
        tool_auth_data = d.get("tool_authorization", {})
        tool_auth = ToolPolicy(
            default_action=tool_auth_data.get("default_action", "deny"),
            roles={
                name: role_data.get("allowed_tools", []) if isinstance(role_data, dict) else role_data
                for name, role_data in tool_auth_data.get("roles", {}).items()
            },
            default_role=tool_auth_data.get("default_role", "reader"),
        )
        budgets_data = d.get("budgets", {})
        budgets = BudgetPolicy(
            max_bundle_chars=budgets_data.get("max_bundle_chars", 40000),
            max_sources=budgets_data.get("max_sources", 50),
            default_k=budgets_data.get("default_k", 12),
            tool_timeouts=budgets_data.get("tool_timeouts", {}),
            cache_ttl_seconds=budgets_data.get("cache_ttl_seconds", 300),
        )
        return cls(
            version=d.get("version", "1.0"),
            persona=persona,
            tool_auth=tool_auth,
            budgets=budgets,
        )

    @classmethod
    def defaults(cls) -> "PolicyBundle":
        """Return default policy matching current hardcoded behavior."""
        return cls(
            version="1.0",
            persona=PersonaPolicy(
                allowed_classifications={
                    "human": ["public", "internal"],
                    "agent": ["public", "internal"],
                    "external": ["public"],
                }
            ),
            tool_auth=ToolPolicy(
                default_action="deny",
                roles={
                    "reader": [
                        "search_repo_memory",
                        "get_context_bundle",
                        "explain_context_bundle",
                        "validate_pack",
                        "list_standards",
                        "get_standard",
                        "get_schema",
                    ],
                    "writer": [
                        "index_repo",
                        "index_all",
                    ],
                },
                default_role="reader",
            ),
            budgets=BudgetPolicy(
                max_bundle_chars=40000,
                max_sources=50,
                default_k=12,
                tool_timeouts={
                    "search_repo_memory": 10,
                    "get_context_bundle": 30,
                    "explain_context_bundle": 5,
                    "validate_pack": 10,
                    "index_repo": 120,
                    "index_all": 300,
                    "list_standards": 5,
                    "get_standard": 5,
                    "get_schema": 5,
                },
                cache_ttl_seconds=300,
            ),
        )
