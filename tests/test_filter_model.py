"""Tests for src.filter_model."""

import pytest
from src.filter_model import ModelFilter, filter_by_model


class TestModelFilter:
    def test_matches_present(self):
        mf = ModelFilter("693b3c0900004140")
        assert mf.matches("GET /m3Batch?model=gomodel:693b3c0900004140 200")

    def test_matches_absent(self):
        mf = ModelFilter("693b3c0900004140")
        assert not mf.matches("GET /search/taxa 200 50ms")

    def test_matches_in_url(self):
        mf = ModelFilter("abc123")
        assert mf.matches("http://model.geneontology.org/abc123/ind1")

    def test_matches_empty_line(self):
        mf = ModelFilter("abc123")
        assert not mf.matches("")


class TestFilterByModel:
    def test_filters_correctly(self, tmp_path):
        log = tmp_path / "input.log"
        log.write_text(
            "line with model 693b3c0900004140 here\n"
            "unrelated line\n"
            "another 693b3c0900004140 match\n"
            "noise\n",
            encoding="utf-8",
        )
        out = tmp_path / "output.log"
        stats = filter_by_model(str(log), "693b3c0900004140", str(out))

        assert stats.total_lines == 4
        assert stats.kept == 2
        lines = out.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert "693b3c0900004140" in lines[0]
        assert "693b3c0900004140" in lines[1]

    def test_no_matches(self, tmp_path):
        log = tmp_path / "input.log"
        log.write_text("no match here\n", encoding="utf-8")
        out = tmp_path / "output.log"
        stats = filter_by_model(str(log), "nonexistent", str(out))

        assert stats.kept == 0
        assert out.read_text(encoding="utf-8") == ""
