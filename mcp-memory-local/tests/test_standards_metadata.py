"""Unit tests for standards service front matter metadata parsing."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "shared", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "standards", "src"))

import pytest
from server import _parse_front_matter, _metadata_cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the metadata cache before each test."""
    _metadata_cache.clear()
    yield
    _metadata_cache.clear()


class TestParseFrontMatter:
    def test_standard_front_matter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text(
            "---\ntitle: Bicep Infrastructure as Code Standards\n"
            "domain: bicep\nstandard_id: enterprise/bicep/infrastructure-as-code\n---\n\n# Content",
            encoding="utf-8",
        )
        result = _parse_front_matter(f)
        assert result["title"] == "Bicep Infrastructure as Code Standards"
        assert result["domain"] == "bicep"

    def test_missing_front_matter_defaults(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("# No front matter here\n\nJust content.", encoding="utf-8")
        result = _parse_front_matter(f)
        assert result["title"] == ""
        assert result["domain"] == ""

    def test_partial_front_matter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\ntitle: Only Title\n---\n\n# Content", encoding="utf-8")
        result = _parse_front_matter(f)
        assert result["title"] == "Only Title"
        assert result["domain"] == ""

    def test_caching(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("---\ntitle: Cached\ndomain: test\n---\n", encoding="utf-8")
        result1 = _parse_front_matter(f)
        # Modify file (cache should still return old value)
        f.write_text("---\ntitle: Changed\ndomain: changed\n---\n", encoding="utf-8")
        result2 = _parse_front_matter(f)
        assert result1 == result2  # Cache hit

    def test_nonexistent_file(self, tmp_path):
        f = tmp_path / "nonexistent.md"
        result = _parse_front_matter(f)
        assert result["title"] == ""
        assert result["domain"] == ""


class TestListStandardsMetadata:
    """Test that list_standards returns metadata from actual standard files."""

    def test_real_standards_have_metadata(self):
        """Verify all 9 enterprise standards have title and domain in front matter."""
        standards_root = Path(os.path.dirname(__file__)) / ".." / "repos" / "enterprise-standards" / ".ai" / "memory" / "enterprise"
        standards_root = standards_root.resolve()
        if not standards_root.exists():
            pytest.skip("Enterprise standards not available")

        for md_file in standards_root.rglob("*.md"):
            result = _parse_front_matter(md_file)
            assert result["title"], f"Missing title in {md_file}"
            assert result["domain"], f"Missing domain in {md_file}"
