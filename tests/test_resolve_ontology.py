"""Tests for src.resolve_ontology."""

import json
import pytest
from unittest.mock import patch
from src.resolve_ontology import (
    collect_ids_from_text,
    collect_ids_from_files,
    load_cache,
    save_cache,
    resolve,
)


class TestCollectIds:
    def test_finds_go_ids(self):
        text = "type: GO:0005200 and GO:0031941"
        ids = collect_ids_from_text(text)
        assert ids == {"GO:0005200", "GO:0031941"}

    def test_finds_eco_ids(self):
        ids = collect_ids_from_text("evidence: ECO:0000305")
        assert ids == {"ECO:0000305"}

    def test_ignores_non_ontology_prefixes(self):
        ids = collect_ids_from_text("PMID:12345678 and SGD:S000003312")
        assert ids == set()

    def test_finds_mixed(self):
        text = "GO:1904600 ECO:0000314 RO:0002333 PMID:99999"
        ids = collect_ids_from_text(text)
        assert "GO:1904600" in ids
        assert "ECO:0000314" in ids
        assert "RO:0002333" in ids
        assert "PMID:99999" not in ids

    def test_short_numbers_ignored(self):
        # IDs need 5+ digits
        ids = collect_ids_from_text("GO:123")
        assert ids == set()

    def test_collect_from_files(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("GO:0005200\n", encoding="utf-8")
        f2.write_text("ECO:0000305\n", encoding="utf-8")
        ids = collect_ids_from_files([str(f1), str(f2)])
        assert ids == {"GO:0005200", "ECO:0000305"}


class TestCache:
    def test_save_and_load(self, tmp_path, monkeypatch):
        cache_path = tmp_path / "ontology_cache.json"
        monkeypatch.setattr("src.resolve_ontology.CACHE_PATH", cache_path)

        save_cache({"GO:0005200": "structural constituent of cytoskeleton"})
        loaded = load_cache()
        assert loaded["GO:0005200"] == "structural constituent of cytoskeleton"

    def test_load_missing_file(self, tmp_path, monkeypatch):
        cache_path = tmp_path / "nonexistent.json"
        monkeypatch.setattr("src.resolve_ontology.CACHE_PATH", cache_path)
        assert load_cache() == {}

    def test_load_corrupt_file(self, tmp_path, monkeypatch):
        cache_path = tmp_path / "bad.json"
        cache_path.write_text("not json{{{", encoding="utf-8")
        monkeypatch.setattr("src.resolve_ontology.CACHE_PATH", cache_path)
        assert load_cache() == {}


class TestResolve:
    def test_all_cached(self, capsys):
        labels = {"GO:0005200": "structural constituent of cytoskeleton"}
        n = resolve({"GO:0005200"}, labels)
        assert n == 0
        assert "already cached" in capsys.readouterr().out

    @patch("src.resolve_ontology.fetch_label", return_value="test label")
    def test_resolves_missing(self, mock_fetch):
        labels = {}
        n = resolve({"GO:0099999"}, labels)
        assert n == 1
        assert labels["GO:0099999"] == "test label"
        mock_fetch.assert_called_once_with("GO:0099999")

    @patch("src.resolve_ontology.fetch_label", return_value=None)
    def test_unresolvable(self, mock_fetch):
        labels = {}
        n = resolve({"GO:0099999"}, labels)
        assert n == 0
        assert "GO:0099999" not in labels
