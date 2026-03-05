"""Structured JSON logging with X-Request-ID tracing (§6.3)."""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

# Context variable for request ID propagation
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get current request ID, or generate a new one."""
    rid = request_id_var.get()
    if not rid:
        rid = str(uuid.uuid4())
        request_id_var.set(rid)
    return rid


def new_request_id() -> str:
    """Generate and set a new request ID."""
    rid = str(uuid.uuid4())
    request_id_var.set(rid)
    return rid


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON lines."""

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S.%fZ"),
            "service": self.service_name,
            "request_id": request_id_var.get(""),
            "tool": getattr(record, "tool", ""),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if record.exc_info and record.exc_info[1]:
            log_entry["error"] = str(record.exc_info[1])
        # Audit log fields
        if getattr(record, "audit", False):
            log_entry["audit"] = True
            for field in ("action", "subject", "repo", "provenance_refs", "correlation_id"):
                val = getattr(record, field, None)
                if val is not None:
                    log_entry[field] = val
            if hasattr(record, "error") and not log_entry.get("error"):
                log_entry["error"] = record.error
        return json.dumps(log_entry)


def setup_logging(service_name: str, level: int = logging.INFO) -> logging.Logger:
    """Configure structured JSON logging for a service."""
    logger = logging.getLogger(service_name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter(service_name))
        logger.addHandler(handler)

    return logger


class TimedOperation:
    """Context manager that logs operation duration."""

    def __init__(self, logger: logging.Logger, tool: str, message: str):
        self.logger = logger
        self.tool = tool
        self.message = message
        self.start = 0.0

    def __enter__(self):
        self.start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = round((time.monotonic() - self.start) * 1000, 2)
        extra = {"tool": self.tool, "duration_ms": duration_ms}
        if exc_val:
            self.logger.error(self.message, extra=extra, exc_info=(exc_type, exc_val, exc_tb))
        else:
            self.logger.info(f"{self.message} completed", extra=extra)
        return False
