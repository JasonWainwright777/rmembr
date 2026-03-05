"""Unit tests for AuditLogger format and fields."""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mcp-memory-local", "services", "shared", "src"))

from audit_log import AuditLogger


class _CaptureHandler(logging.Handler):
    """Captures log records for testing."""
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def _make_logger():
    logger = logging.getLogger("test_audit")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    handler = _CaptureHandler()
    logger.addHandler(handler)
    return logger, handler


def test_log_tool_call_invoke():
    logger, handler = _make_logger()
    audit = AuditLogger(logger)
    audit.log_tool_call(
        tool="search_repo_memory",
        action="invoke",
        subject="reader",
        repo="my-repo",
        correlation_id="req-123",
        duration_ms=42.5,
    )
    assert len(handler.records) == 1
    record = handler.records[0]
    assert record.audit is True
    assert record.tool == "search_repo_memory"
    assert record.action == "invoke"
    assert record.subject == "reader"
    assert record.repo == "my-repo"
    assert record.correlation_id == "req-123"
    assert record.duration_ms == 42.5
    assert hasattr(record, "timestamp")


def test_log_tool_call_deny():
    logger, handler = _make_logger()
    audit = AuditLogger(logger)
    audit.log_tool_call(
        tool="index_repo",
        action="deny",
        subject="reader",
        correlation_id="req-456",
    )
    assert len(handler.records) == 1
    record = handler.records[0]
    assert record.audit is True
    assert record.action == "deny"
    assert record.tool == "index_repo"
    assert record.subject == "reader"


def test_log_tool_call_error():
    logger, handler = _make_logger()
    audit = AuditLogger(logger)
    audit.log_tool_call(
        tool="get_context_bundle",
        action="error",
        subject="reader",
        repo="my-repo",
        correlation_id="req-789",
        duration_ms=100.0,
        error="Connection timeout",
    )
    assert len(handler.records) == 1
    record = handler.records[0]
    assert record.audit is True
    assert record.action == "error"
    assert record.error == "Connection timeout"


def test_log_tool_call_with_provenance_refs():
    logger, handler = _make_logger()
    audit = AuditLogger(logger)
    audit.log_tool_call(
        tool="search_repo_memory",
        action="invoke",
        subject="reader",
        provenance_refs=["filesystem", "github"],
        correlation_id="req-aaa",
    )
    record = handler.records[0]
    assert record.provenance_refs == ["filesystem", "github"]


def test_log_tool_call_defaults():
    logger, handler = _make_logger()
    audit = AuditLogger(logger)
    audit.log_tool_call(
        tool="list_standards",
        action="invoke",
        subject="anonymous",
    )
    record = handler.records[0]
    assert record.repo == ""
    assert record.provenance_refs == []
    assert record.correlation_id == ""


def test_audit_record_has_required_fields():
    """Verify all required audit fields are present."""
    logger, handler = _make_logger()
    audit = AuditLogger(logger)
    audit.log_tool_call(
        tool="get_schema",
        action="invoke",
        subject="reader",
        correlation_id="test-corr",
    )
    record = handler.records[0]
    required_fields = ["audit", "tool", "action", "subject", "correlation_id", "timestamp"]
    for field in required_fields:
        assert hasattr(record, field), f"Missing required field: {field}"
