"""Tests for src.resolve_metadata."""

import json
import pytest
from src.resolve_metadata import (
    load_cache,
    save_cache,
    substitute_metadata,
)


class TestCache:
    def test_save_and_load(self, tmp_path, monkeypatch):
        cache_path = tmp_path / "metadata_cache.json"
        monkeypatch.setattr("src.resolve_metadata.CACHE_PATH", cache_path)

        data = {
            "users": {"https://orcid.org/0000-0001-6330-7526": "Val Wood"},
            "groups": {"http://www.pombase.org": "PomBase"},
        }
        save_cache(data)
        loaded = load_cache()
        assert loaded["users"]["https://orcid.org/0000-0001-6330-7526"] == "Val Wood"
        assert loaded["groups"]["http://www.pombase.org"] == "PomBase"

    def test_load_missing_file(self, tmp_path, monkeypatch):
        cache_path = tmp_path / "nonexistent.json"
        monkeypatch.setattr("src.resolve_metadata.CACHE_PATH", cache_path)
        result = load_cache()
        assert result == {"users": {}, "groups": {}}

    def test_load_corrupt_file(self, tmp_path, monkeypatch):
        cache_path = tmp_path / "bad.json"
        cache_path.write_text("{bad", encoding="utf-8")
        monkeypatch.setattr("src.resolve_metadata.CACHE_PATH", cache_path)
        assert load_cache() == {"users": {}, "groups": {}}


class TestSubstituteMetadata:
    CACHE = {
        "users": {
            "https://orcid.org/0000-0001-6330-7526": "Val Wood",
            "https://orcid.org/0000-0002-1234-5678": "Jane Doe",
        },
        "groups": {
            "http://www.pombase.org": "PomBase",
            "http://geneontology.org": "GO_Central",
        },
    }

    def test_replaces_contributor(self):
        text = "contributor: https://orcid.org/0000-0001-6330-7526"
        result = substitute_metadata(text, self.CACHE)
        assert result == "contributor: Val Wood (https://orcid.org/0000-0001-6330-7526)"

    def test_replaces_provided_by(self):
        text = "providedBy: http://www.pombase.org"
        result = substitute_metadata(text, self.CACHE)
        assert result == "providedBy: PomBase (http://www.pombase.org)"

    def test_replaces_by_provider(self):
        text = "ACTION by http://www.pombase.org [ops]"
        result = substitute_metadata(text, self.CACHE)
        assert "by PomBase (http://www.pombase.org)" in result

    def test_unknown_orcid_unchanged(self):
        text = "contributor: https://orcid.org/9999-9999-9999-9999"
        result = substitute_metadata(text, self.CACHE)
        assert result == text

    def test_unknown_group_unchanged(self):
        text = "providedBy: http://unknown.org"
        result = substitute_metadata(text, self.CACHE)
        assert result == text

    def test_multiple_substitutions(self):
        text = (
            "contributor: https://orcid.org/0000-0001-6330-7526\n"
            "providedBy: http://www.pombase.org\n"
            "contributor: https://orcid.org/0000-0002-1234-5678\n"
        )
        result = substitute_metadata(text, self.CACHE)
        assert "Val Wood" in result
        assert "PomBase" in result
        assert "Jane Doe" in result

    def test_empty_cache(self):
        text = "contributor: https://orcid.org/0000-0001-6330-7526"
        result = substitute_metadata(text, {"users": {}, "groups": {}})
        assert result == text

    def test_no_false_positives(self):
        text = "some random text without any URIs"
        result = substitute_metadata(text, self.CACHE)
        assert result == text
