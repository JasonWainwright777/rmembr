"""Unit tests for task-aware standard selection (gateway _select_standards)."""

import os
import sys

# Ensure shared lib + gateway paths are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "shared", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "gateway", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "gateway"))

import pytest


# --- Fixtures: sample standards list (mimics list_standards response with metadata) ---

AVAILABLE_STANDARDS = [
    {"id": "enterprise/bicep/infrastructure-as-code", "version": "local", "title": "Bicep Infrastructure as Code Standards", "domain": "bicep"},
    {"id": "enterprise/terraform/module-versioning", "version": "local", "title": "Terraform Module Versioning Standards", "domain": "terraform"},
    {"id": "enterprise/api/rest-api-design", "version": "local", "title": "REST API Design Standard", "domain": "api"},
    {"id": "enterprise/dotnet/application-standards", "version": "local", "title": ".NET Application Standards", "domain": "dotnet"},
    {"id": "enterprise/security/secrets-management", "version": "local", "title": "Secrets Management Standard", "domain": "security"},
    {"id": "enterprise/ado/pipelines/job-templates-v3", "version": "local", "title": "ADO Pipeline Job Templates", "domain": "ado"},
    {"id": "enterprise/docker/container-standards", "version": "local", "title": "Docker Container Standards", "domain": "docker"},
    {"id": "enterprise/observability/logging-and-monitoring", "version": "local", "title": "Logging and Monitoring Standard", "domain": "observability"},
    {"id": "enterprise/testing/quality-gates", "version": "local", "title": "Testing Quality Gates", "domain": "testing"},
]


# Import the functions under test
from src.server import _select_standards, _tokenize


class TestTokenize:
    def test_basic_tokenization(self):
        tokens = _tokenize("Write a Bicep module for storage")
        assert "bicep" in tokens
        assert "module" in tokens
        assert "storage" in tokens
        # Stopwords removed
        assert "a" not in tokens
        assert "for" not in tokens

    def test_stopword_removal(self):
        tokens = _tokenize("write a new bicep template")
        assert "write" not in tokens  # in stopwords
        assert "a" not in tokens
        assert "new" not in tokens
        assert "bicep" in tokens
        assert "template" in tokens

    def test_case_insensitive(self):
        tokens = _tokenize("BICEP Infrastructure")
        assert "bicep" in tokens
        assert "infrastructure" in tokens

    def test_empty_string(self):
        tokens = _tokenize("")
        assert tokens == set()


class TestSelectStandards:
    def test_bicep_task_selects_bicep_standard(self):
        selected = _select_standards(
            "write a Bicep module for storage",
            AVAILABLE_STANDARDS, [], max_standards=5,
        )
        selected_ids = [s["id"] for s in selected]
        assert "enterprise/bicep/infrastructure-as-code" in selected_ids

    def test_bicep_task_excludes_ado(self):
        selected = _select_standards(
            "write a Bicep module for storage",
            AVAILABLE_STANDARDS, [], max_standards=5,
        )
        selected_ids = [s["id"] for s in selected]
        assert "enterprise/ado/pipelines/job-templates-v3" not in selected_ids

    def test_dotnet_api_task_selects_both(self):
        selected = _select_standards(
            "add a .NET API endpoint for user profiles",
            AVAILABLE_STANDARDS, [], max_standards=5,
        )
        selected_ids = [s["id"] for s in selected]
        assert "enterprise/dotnet/application-standards" in selected_ids
        assert "enterprise/api/rest-api-design" in selected_ids

    def test_pinned_standards_always_included(self):
        pinned = ["enterprise/security/secrets-management"]
        selected = _select_standards(
            "write a Bicep module for storage",
            AVAILABLE_STANDARDS, pinned, max_standards=5,
        )
        selected_ids = [s["id"] for s in selected]
        assert "enterprise/security/secrets-management" in selected_ids
        # And bicep should still match
        assert "enterprise/bicep/infrastructure-as-code" in selected_ids

    def test_pinned_labeled_as_pinned(self):
        pinned = ["enterprise/security/secrets-management"]
        selected = _select_standards(
            "write a Bicep module",
            AVAILABLE_STANDARDS, pinned, max_standards=5,
        )
        for s in selected:
            if s["id"] == "enterprise/security/secrets-management":
                assert s["_selection_reason"] == "pinned"
                break
        else:
            pytest.fail("Pinned standard not found in selection")

    def test_matched_labeled_as_keyword_match(self):
        selected = _select_standards(
            "write a Bicep module",
            AVAILABLE_STANDARDS, [], max_standards=5,
        )
        for s in selected:
            if s["id"] == "enterprise/bicep/infrastructure-as-code":
                assert s["_selection_reason"] == "keyword_match"
                break
        else:
            pytest.fail("Bicep standard not found in selection")

    def test_max_standards_budget_respected(self):
        selected = _select_standards(
            "bicep terraform api dotnet security ado docker observability testing",
            AVAILABLE_STANDARDS, [], max_standards=3,
        )
        assert len(selected) <= 3

    def test_pinned_count_toward_budget(self):
        pinned = [
            "enterprise/security/secrets-management",
            "enterprise/bicep/infrastructure-as-code",
            "enterprise/api/rest-api-design",
        ]
        selected = _select_standards(
            "bicep terraform api dotnet security ado docker",
            AVAILABLE_STANDARDS, pinned, max_standards=3,
        )
        # Should be exactly 3 (all pinned), no room for keyword matches
        assert len(selected) == 3
        selected_ids = [s["id"] for s in selected]
        for p in pinned:
            assert p in selected_ids

    def test_no_keyword_overlap_returns_empty(self):
        selected = _select_standards(
            "general question about the repo",
            AVAILABLE_STANDARDS, [], max_standards=5,
        )
        assert len(selected) == 0

    def test_terraform_task(self):
        selected = _select_standards(
            "create Terraform modules for networking",
            AVAILABLE_STANDARDS, [], max_standards=5,
        )
        selected_ids = [s["id"] for s in selected]
        assert "enterprise/terraform/module-versioning" in selected_ids

    def test_docker_task(self):
        selected = _select_standards(
            "build a Docker container for the API",
            AVAILABLE_STANDARDS, [], max_standards=5,
        )
        selected_ids = [s["id"] for s in selected]
        assert "enterprise/docker/container-standards" in selected_ids
        assert "enterprise/api/rest-api-design" in selected_ids

    def test_scores_included_in_results(self):
        selected = _select_standards(
            "write Bicep infrastructure",
            AVAILABLE_STANDARDS, [], max_standards=5,
        )
        for s in selected:
            assert "_selection_score" in s
            assert "_matched_keywords" in s
            assert s["_selection_score"] > 0

    def test_empty_available_returns_empty(self):
        selected = _select_standards("write bicep", [], [], max_standards=5)
        assert selected == []

    def test_pinned_not_in_available_skipped(self):
        """Pinned standard that doesn't exist in available list is simply skipped."""
        pinned = ["enterprise/nonexistent/standard"]
        selected = _select_standards(
            "write Bicep module",
            AVAILABLE_STANDARDS, pinned, max_standards=5,
        )
        selected_ids = [s["id"] for s in selected]
        assert "enterprise/nonexistent/standard" not in selected_ids
        # But bicep should still match
        assert "enterprise/bicep/infrastructure-as-code" in selected_ids
