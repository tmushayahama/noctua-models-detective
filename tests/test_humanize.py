"""Tests for src.humanize."""

import json
import pytest
from unittest.mock import patch
from src.humanize import (
    substitute_ontology_labels,
    Operation,
    LogEntry,
    BodyDataParser,
    LogEntryParser,
    HumanFormatter,
)


class TestSubstituteOntologyLabels:
    @patch("src.humanize._load_ontology_labels", return_value={
        "GO:0005200": "structural constituent of cytoskeleton",
        "ECO:0000305": "curator inference used in manual assertion",
    })
    def test_replaces_bare_ids(self, mock_load):
        text = "type: GO:0005200"
        result = substitute_ontology_labels(text)
        assert result == "type: structural constituent of cytoskeleton (GO:0005200)"

    @patch("src.humanize._load_ontology_labels", return_value={
        "GO:0005200": "structural constituent of cytoskeleton",
    })
    def test_no_double_substitution(self, mock_load):
        text = "type: structural constituent of cytoskeleton (GO:0005200)"
        result = substitute_ontology_labels(text)
        # Should not become "label (label (GO:0005200))"
        assert result == text

    @patch("src.humanize._load_ontology_labels", return_value={})
    def test_empty_cache_unchanged(self, mock_load):
        text = "type: GO:0005200"
        result = substitute_ontology_labels(text)
        assert result == text

    @patch("src.humanize._load_ontology_labels", return_value={
        "GO:1904600": "mating projection actin fusion focus assembly",
    })
    def test_unknown_id_unchanged(self, mock_load):
        text = "type: GO:9999999"
        result = substitute_ontology_labels(text)
        assert result == text

    @patch("src.humanize._load_ontology_labels", return_value={})
    def test_non_ontology_prefix_ignored(self, mock_load):
        text = "PMID:12345678"
        result = substitute_ontology_labels(text)
        assert result == text


class TestOperation:
    def test_format_basic(self):
        op = Operation(entity="individual", operation="add-type")
        result = op.format()
        assert "individual.add-type" in result

    def test_format_edge(self):
        op = Operation(
            entity="edge",
            operation="add",
            arguments={
                "subject": "http://model.geneontology.org/m/sub1",
                "predicate": "part_of",
                "object": "http://model.geneontology.org/m/obj1",
            },
        )
        result = op.format()
        assert "sub1 --part_of--> obj1" in result

    def test_format_expressions(self):
        op = Operation(
            entity="individual",
            operation="add-type",
            arguments={
                "expressions": [{"type": "class", "id": "GO:0005200"}],
            },
        )
        result = op.format()
        assert "class: GO:0005200" in result


class TestBodyDataParser:
    def test_parse_with_requests(self):
        raw = (
            'intention=action&'
            'provided-by=http%3A%2F%2Fwww.pombase.org&'
            'requests=%5B%7B%22entity%22%3A%22individual%22%2C'
            '%22operation%22%3A%22add-type%22%2C%22arguments%22%3A%7B%7D%7D%5D'
        )
        metadata, ops = BodyDataParser.parse(raw)
        assert metadata["intention"] == "action"
        assert metadata["provided-by"] == "http://www.pombase.org"
        assert len(ops) == 1
        assert ops[0].entity == "individual"
        assert ops[0].operation == "add-type"

    def test_parse_empty(self):
        metadata, ops = BodyDataParser.parse("")
        assert ops == []

    def test_parse_bad_json(self):
        raw = "intention=action&requests=not_json"
        metadata, ops = BodyDataParser.parse(raw)
        assert metadata["intention"] == "action"
        assert ops == []


class TestLogEntryParser:
    def test_parse_barista_api_xlate(self, tmp_path):
        log = tmp_path / "test.log"
        log.write_text(
            'barista [2026-02-20T10:00:00.000Z]:  api xlate (GET): [http://toaster:6800]/m3Batch?id=123\n',
            encoding="utf-8",
        )
        parser = LogEntryParser()
        entries = parser.parse(str(log))
        assert len(entries) == 1
        assert entries[0].entry_type == "api"
        assert "API GET /m3Batch" in entries[0].summary

    def test_parse_http_access(self, tmp_path):
        log = tmp_path / "test.log"
        log.write_text("GET /m3Batch 200 50.0 ms - 1234\n", encoding="utf-8")
        parser = LogEntryParser()
        entries = parser.parse(str(log))
        assert len(entries) == 1
        assert entries[0].entry_type == "http"
        assert "200" in entries[0].summary

    def test_parse_ignores_junk(self, tmp_path):
        log = tmp_path / "test.log"
        log.write_text("random noise line\n", encoding="utf-8")
        parser = LogEntryParser()
        entries = parser.parse(str(log))
        assert len(entries) == 0


class TestHumanFormatter:
    def test_format_with_date_header(self):
        entries = [
            LogEntry(
                timestamp="2026-02-20T10:00:00.000Z",
                entry_type="api",
                summary="API GET /m3Batch",
            ),
        ]
        text = HumanFormatter.format(entries)
        assert "2026-02-20" in text
        assert "API GET /m3Batch" in text
        assert "[API  ]" in text

    def test_format_date_change(self):
        entries = [
            LogEntry(timestamp="2026-02-20T10:00:00.000Z", entry_type="api", summary="a"),
            LogEntry(timestamp="2026-02-21T10:00:00.000Z", entry_type="api", summary="b"),
        ]
        text = HumanFormatter.format(entries)
        assert "2026-02-20" in text
        assert "2026-02-21" in text

    def test_format_empty(self):
        text = HumanFormatter.format([])
        assert text == "\n"
