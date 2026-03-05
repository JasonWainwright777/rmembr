"""Structured audit log for tool call events."""

import time


class AuditLogger:
    """Structured audit log for tool call events."""

    def __init__(self, logger):
        self.logger = logger

    def log_tool_call(
        self,
        tool: str,
        action: str,  # "invoke", "deny", "error"
        subject: str,  # caller identity (role or "anonymous")
        repo: str | None = None,
        provenance_refs: list[str] | None = None,
        correlation_id: str = "",
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> None:
        """Emit a structured audit log record."""
        record = {
            "audit": True,
            "tool": tool,
            "action": action,
            "subject": subject,
            "repo": repo or "",
            "provenance_refs": provenance_refs or [],
            "correlation_id": correlation_id,
            "timestamp": time.time(),
        }
        if duration_ms is not None:
            record["duration_ms"] = duration_ms
        if error:
            record["error"] = error
        self.logger.info("audit_event", extra=record)
