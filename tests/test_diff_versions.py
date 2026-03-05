"""Tests for src.diff_versions."""

import pytest
from unittest.mock import patch
from src.diff_versions import Uri, Individual, TtlParser, SemanticDiff, VersionDiffer


class TestUri:
    def test_shorten_go(self):
        assert Uri.shorten("http://purl.obolibrary.org/obo/GO_0005200") == "GO:0005200"

    def test_shorten_eco(self):
        assert Uri.shorten("http://purl.obolibrary.org/obo/ECO_0000305") == "ECO:0000305"

    def test_shorten_bfo_occurs_in(self):
        assert Uri.shorten("http://purl.obolibrary.org/obo/BFO_0000066") == "occurs_in"

    def test_shorten_bfo_part_of(self):
        assert Uri.shorten("http://purl.obolibrary.org/obo/BFO_0000050") == "part_of"

    def test_shorten_ro_enabled_by(self):
        assert Uri.shorten("http://purl.obolibrary.org/obo/RO_0002333") == "enabled_by"

    def test_shorten_identifiers_org(self):
        assert Uri.shorten("http://identifiers.org/pombase/SPBC32H8.12c") == "pombase:SPBC32H8.12c"

    def test_shorten_model_individual(self):
        result = Uri.shorten("http://model.geneontology.org/693b3c0900004140/ind1")
        assert result == "ind1"

    def test_shorten_unknown_passthrough(self):
        uri = "http://example.com/unknown"
        assert Uri.shorten(uri) == uri


class TestIndividual:
    def test_type_label_go(self):
        ind = Individual(
            uri="http://example.com/ind1",
            short_id="ind1",
            types=["http://www.w3.org/2002/07/owl#NamedIndividual",
                   "http://purl.obolibrary.org/obo/GO_0005200"],
        )
        assert ind.type_label() == "GO:0005200"

    def test_type_label_only_named_individual(self):
        ind = Individual(
            uri="http://example.com/ind1",
            short_id="ind1",
            types=["http://www.w3.org/2002/07/owl#NamedIndividual"],
        )
        assert ind.type_label() == "NamedIndividual"


class TestTtlParser:
    MINIMAL_TTL = """\
<http://model.geneontology.org/test/ind1> a <http://www.w3.org/2002/07/owl#NamedIndividual> , <http://purl.obolibrary.org/obo/GO_0005200> ;
\t<http://purl.org/dc/elements/1.1/contributor> "Val Wood" ;
\t<http://purl.org/dc/elements/1.1/date> "2026-02-20" .
"""

    def test_parse_individual(self, tmp_path):
        ttl = tmp_path / "test.ttl"
        ttl.write_text(self.MINIMAL_TTL, encoding="utf-8")
        parser = TtlParser()
        inds = parser.parse(str(ttl))
        assert len(inds) == 1
        ind = list(inds.values())[0]
        assert ind.type_label() == "GO:0005200"
        assert ind.annotations.get("contributor") == "Val Wood"
        assert ind.annotations.get("date") == "2026-02-20"

    def test_parse_empty_file(self, tmp_path):
        ttl = tmp_path / "empty.ttl"
        ttl.write_text("", encoding="utf-8")
        parser = TtlParser()
        assert parser.parse(str(ttl)) == {}


class TestSemanticDiff:
    def _make_ind(self, short_id, go_type, **annotations):
        return Individual(
            uri=f"http://model.geneontology.org/test/{short_id}",
            short_id=short_id,
            types=[
                "http://www.w3.org/2002/07/owl#NamedIndividual",
                f"http://purl.obolibrary.org/obo/GO_{go_type}",
            ],
            annotations=annotations,
        )

    def test_added_individual(self):
        old = {}
        new = {"ind1": self._make_ind("ind1", "0005200", date="2026-02-20")}
        diff = SemanticDiff()
        text = diff.diff(old, new, "v1", "v2")
        assert "+ ADDED  ind1" in text
        assert "GO:0005200" in text
        assert "+1 individuals added" in text

    def test_removed_individual(self):
        old = {"ind1": self._make_ind("ind1", "0005200")}
        new = {}
        diff = SemanticDiff()
        text = diff.diff(old, new, "v1", "v2")
        assert "- REMOVED  ind1" in text
        assert "-1 removed" in text

    def test_modified_type(self):
        old = {"ind1": self._make_ind("ind1", "0005200")}
        new = {"ind1": self._make_ind("ind1", "0031941")}
        diff = SemanticDiff()
        text = diff.diff(old, new, "v1", "v2")
        assert "~ CHANGED  ind1" in text
        assert "GO:0005200" in text
        assert "GO:0031941" in text

    def test_no_changes(self):
        ind = self._make_ind("ind1", "0005200", date="2026-02-20")
        diff = SemanticDiff()
        text = diff.diff({"ind1": ind}, {"ind1": ind}, "v1", "v2")
        assert "~0 modified" in text

    def test_annotation_change(self):
        old = {"ind1": self._make_ind("ind1", "0005200", date="2025-01-01")}
        new = {"ind1": self._make_ind("ind1", "0005200", date="2026-02-20")}
        diff = SemanticDiff()
        text = diff.diff(old, new, "v1", "v2")
        assert "2025-01-01" in text
        assert "2026-02-20" in text

    def test_header_format(self):
        diff = SemanticDiff()
        text = diff.diff({}, {}, "2026-02-20_08-00", "2026-02-20_09-00")
        assert "2026-02-20_08-00  →  2026-02-20_09-00" in text


class TestResolveMissingIds:
    @patch("src.resolve_ontology.save_cache")
    @patch("src.resolve_ontology.resolve", return_value=1)
    @patch("src.resolve_ontology.load_cache", return_value={"GO:0005200": "cached"})
    def test_resolves_missing_ids(self, mock_load, mock_resolve, mock_save):
        text = "type: GO:0005200  →  GO:0140378"
        VersionDiffer._resolve_missing_ids(text)
        mock_resolve.assert_called_once()
        # Should only resolve GO:0140378, not GO:0005200 (already cached)
        ids_arg = mock_resolve.call_args[0][0]
        assert "GO:0140378" in ids_arg
        assert "GO:0005200" not in ids_arg
        mock_save.assert_called_once()

    @patch("src.resolve_ontology.load_cache", return_value={"GO:0005200": "cached"})
    def test_skips_when_all_cached(self, mock_load):
        text = "type: GO:0005200"
        VersionDiffer._resolve_missing_ids(text)
        # load_cache called, but no resolve call needed

    @patch("src.resolve_ontology.save_cache")
    @patch("src.resolve_ontology.resolve", return_value=0)
    @patch("src.resolve_ontology.load_cache", return_value={})
    def test_no_save_when_nothing_resolved(self, mock_load, mock_resolve, mock_save):
        text = "type: GO:0140378"
        VersionDiffer._resolve_missing_ids(text)
        mock_resolve.assert_called_once()
        mock_save.assert_not_called()
