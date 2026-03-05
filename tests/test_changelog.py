"""Tests for src.changelog."""

import pytest
from src.changelog import (
    ChangeEntry,
    VersionDiff,
    ChangelogStats,
    parse_changes,
    generate_changelog_md,
    generate_changelog,
    _format_entry_md,
    _summarize_diff,
)


# ---------------------------------------------------------------------------
# Fixtures and sample data
# ---------------------------------------------------------------------------

SAMPLE_INPUT = """\
======================================================================
  2026-02-12_13-25-14  →  2026-02-12_14-20-41
======================================================================
  +0 individuals added, -0 removed, ~0 modified
  (axiom annotation / blank node reordering only)


======================================================================
  2026-02-12_14-20-41  →  2026-02-20_00-55-01
======================================================================
  +0 individuals added, -0 removed, ~2 modified

  ~ CHANGED  693b3c0900004188
           type: adaptor activity (GO:0030674)  →  GO:0140378
           date: 2025-12-31  →  2026-02-20
  ~ CHANGED  693b3c0900004191
           date: 2025-12-31  →  2026-02-20

======================================================================
  2026-02-20_00-55-01  →  2026-02-20_07-55-01
======================================================================
  +3 individuals added, -0 removed, ~0 modified

  + ADDED  6994852c00002749
           type: mating projection (GO:1990819)
           contributor: Val Wood
           date: 2026-02-20
           providedBy: PomBase
  + ADDED  6994852c00002750
           type: curator inference (ECO:0000305)
           contributor: Val Wood
           date: 2026-02-20
  + ADDED  6994852c00002751
           type: structural constituent of cytoskeleton (GO:0005200)
           occurs_in: 6994852c00002754
           enabled_by: 6994852c00002752
           contributor: Val Wood
           date: 2026-02-20
"""

REMOVALS_INPUT = """\
======================================================================
  2026-02-20_07-55-01  →  2026-02-20_08-00-02
======================================================================
  +0 individuals added, -5 removed, ~1 modified

  - REMOVED  693b3c0900004322
             type: author statement (ECO:0000303)
  - REMOVED  693b3c0900004323
             type: author statement (ECO:0000303)
  - REMOVED  693b3c0900004324
             type: author statement (ECO:0000303)
  - REMOVED  693b3c0900004336
             type: author statement (ECO:0000303)
  - REMOVED  693b3c0900004337
             type: author statement (ECO:0000303)
  ~ CHANGED  6994852c00002751
           + directly_provides_input_for: 693b3c0900004317
"""

MIXED_TYPES_REMOVED_INPUT = """\
======================================================================
  2026-03-01_10-00-00  →  2026-03-01_11-00-00
======================================================================
  +0 individuals added, -4 removed, ~0 modified

  - REMOVED  aaa001
             type: type A
  - REMOVED  aaa002
             type: type A
  - REMOVED  bbb001
             type: type B
  - REMOVED  bbb002
             type: type B
"""

MULTI_DATE_INPUT = """\
======================================================================
  2026-02-10_10-00-00  →  2026-02-10_11-00-00
======================================================================
  +1 individuals added, -0 removed, ~0 modified

  + ADDED  ind001
           type: some type (GO:0001234)

======================================================================
  2026-02-11_10-00-00  →  2026-02-11_11-00-00
======================================================================
  +0 individuals added, -1 removed, ~0 modified

  - REMOVED  ind002
             type: other type (GO:0005678)

======================================================================
  2026-02-12_10-00-00  →  2026-02-12_11-00-00
======================================================================
  +0 individuals added, -0 removed, ~0 modified
  (axiom annotation / blank node reordering only)
"""


# ---------------------------------------------------------------------------
# ChangeEntry dataclass
# ---------------------------------------------------------------------------

class TestChangeEntry:
    def test_defaults(self):
        e = ChangeEntry(action="added", short_id="abc")
        assert e.details == []

    def test_with_details(self):
        e = ChangeEntry(action="changed", short_id="x", details=["type: foo → bar"])
        assert len(e.details) == 1


# ---------------------------------------------------------------------------
# VersionDiff dataclass
# ---------------------------------------------------------------------------

class TestVersionDiff:
    def test_date_from_new_ts(self):
        d = VersionDiff(old_ts="2026-02-12_13-25-14", new_ts="2026-02-20_00-55-01")
        assert d.date == "2026-02-20"

    def test_old_time(self):
        d = VersionDiff(old_ts="2026-02-12_13-25-14", new_ts="2026-02-20_00-55-01")
        assert d.old_time == "13:25:14"

    def test_new_time(self):
        d = VersionDiff(old_ts="2026-02-12_13-25-14", new_ts="2026-02-20_00-55-01")
        assert d.new_time == "00:55:01"

    def test_is_empty_true(self):
        d = VersionDiff(old_ts="a", new_ts="b", added=0, removed=0, modified=0)
        assert d.is_empty is True

    def test_is_empty_false_added(self):
        d = VersionDiff(old_ts="a", new_ts="b", added=1)
        assert d.is_empty is False

    def test_is_empty_false_removed(self):
        d = VersionDiff(old_ts="a", new_ts="b", removed=1)
        assert d.is_empty is False

    def test_is_empty_false_modified(self):
        d = VersionDiff(old_ts="a", new_ts="b", modified=1)
        assert d.is_empty is False


# ---------------------------------------------------------------------------
# ChangelogStats
# ---------------------------------------------------------------------------

class TestChangelogStats:
    def test_str(self):
        s = ChangelogStats(diffs_parsed=5, dates=2, total_changes=10)
        assert "5 diffs parsed" in str(s)
        assert "2 dates" in str(s)
        assert "10 individual changes" in str(s)

    def test_defaults(self):
        s = ChangelogStats()
        assert s.diffs_parsed == 0
        assert s.dates == 0
        assert s.total_changes == 0


# ---------------------------------------------------------------------------
# parse_changes
# ---------------------------------------------------------------------------

class TestParseChanges:
    def test_parses_correct_number_of_diffs(self):
        diffs = parse_changes(SAMPLE_INPUT)
        assert len(diffs) == 3

    def test_first_diff_timestamps(self):
        diffs = parse_changes(SAMPLE_INPUT)
        assert diffs[0].old_ts == "2026-02-12_13-25-14"
        assert diffs[0].new_ts == "2026-02-12_14-20-41"

    def test_first_diff_is_axiom_only(self):
        diffs = parse_changes(SAMPLE_INPUT)
        assert diffs[0].axiom_only is True
        assert diffs[0].is_empty is True
        assert diffs[0].entries == []

    def test_axiom_only_counts_zero(self):
        diffs = parse_changes(SAMPLE_INPUT)
        assert diffs[0].added == 0
        assert diffs[0].removed == 0
        assert diffs[0].modified == 0

    def test_non_axiom_diff_flag_false(self):
        diffs = parse_changes(SAMPLE_INPUT)
        assert diffs[1].axiom_only is False

    def test_second_diff_summary_counts(self):
        diffs = parse_changes(SAMPLE_INPUT)
        assert diffs[1].added == 0
        assert diffs[1].removed == 0
        assert diffs[1].modified == 2

    def test_second_diff_has_two_changed_entries(self):
        diffs = parse_changes(SAMPLE_INPUT)
        assert len(diffs[1].entries) == 2
        assert all(e.action == "changed" for e in diffs[1].entries)

    def test_changed_entry_short_ids(self):
        diffs = parse_changes(SAMPLE_INPUT)
        ids = [e.short_id for e in diffs[1].entries]
        assert "693b3c0900004188" in ids
        assert "693b3c0900004191" in ids

    def test_changed_entry_details_parsed(self):
        diffs = parse_changes(SAMPLE_INPUT)
        entry = diffs[1].entries[0]  # 693b3c0900004188
        assert any("type:" in d for d in entry.details)
        assert any("date:" in d for d in entry.details)

    def test_changed_entry_arrow_in_details(self):
        diffs = parse_changes(SAMPLE_INPUT)
        entry = diffs[1].entries[0]
        type_detail = [d for d in entry.details if d.startswith("type:")][0]
        assert "→" in type_detail

    def test_third_diff_has_additions(self):
        diffs = parse_changes(SAMPLE_INPUT)
        assert diffs[2].added == 3
        assert len(diffs[2].entries) == 3
        assert all(e.action == "added" for e in diffs[2].entries)

    def test_added_entry_short_id(self):
        diffs = parse_changes(SAMPLE_INPUT)
        assert diffs[2].entries[0].short_id == "6994852c00002749"

    def test_added_entry_details_include_type(self):
        diffs = parse_changes(SAMPLE_INPUT)
        entry = diffs[2].entries[0]
        assert any("type:" in d for d in entry.details)

    def test_added_entry_details_include_contributor(self):
        diffs = parse_changes(SAMPLE_INPUT)
        entry = diffs[2].entries[0]
        assert any("contributor:" in d for d in entry.details)

    def test_added_entry_details_include_date(self):
        diffs = parse_changes(SAMPLE_INPUT)
        entry = diffs[2].entries[0]
        assert any("date:" in d for d in entry.details)

    def test_added_entry_details_include_provided_by(self):
        diffs = parse_changes(SAMPLE_INPUT)
        entry = diffs[2].entries[0]
        assert any("providedBy:" in d for d in entry.details)

    def test_added_entry_with_relationships(self):
        diffs = parse_changes(SAMPLE_INPUT)
        entry = diffs[2].entries[2]  # 6994852c00002751
        assert any("occurs_in:" in d for d in entry.details)
        assert any("enabled_by:" in d for d in entry.details)

    def test_parse_removals(self):
        diffs = parse_changes(REMOVALS_INPUT)
        assert len(diffs) == 1
        assert diffs[0].removed == 5
        removed = [e for e in diffs[0].entries if e.action == "removed"]
        assert len(removed) == 5

    def test_removed_entry_has_type_detail(self):
        diffs = parse_changes(REMOVALS_INPUT)
        entry = diffs[0].entries[0]
        assert entry.action == "removed"
        assert any("type:" in d for d in entry.details)

    def test_parse_changed_with_added_relationship(self):
        diffs = parse_changes(REMOVALS_INPUT)
        changed = [e for e in diffs[0].entries if e.action == "changed"]
        assert len(changed) == 1
        assert any("+ directly_provides_input_for:" in d for d in changed[0].details)

    def test_empty_input(self):
        assert parse_changes("") == []

    def test_only_separator_lines(self):
        assert parse_changes("=" * 70 + "\n" + "=" * 70) == []

    def test_single_diff_block(self):
        text = """\
======================================================================
  2026-01-01_00-00-00  →  2026-01-01_01-00-00
======================================================================
  +1 individuals added, -0 removed, ~0 modified

  + ADDED  ind1
           type: something
"""
        diffs = parse_changes(text)
        assert len(diffs) == 1
        assert diffs[0].added == 1
        assert diffs[0].entries[0].short_id == "ind1"

    def test_last_entry_finalized(self):
        """The last entry in the last diff should be captured."""
        text = """\
======================================================================
  2026-01-01_00-00-00  →  2026-01-01_01-00-00
======================================================================
  +0 individuals added, -0 removed, ~1 modified

  ~ CHANGED  x
           date: old  →  new"""
        diffs = parse_changes(text)
        assert len(diffs[0].entries) == 1
        assert diffs[0].entries[0].short_id == "x"
        assert len(diffs[0].entries[0].details) == 1


# ---------------------------------------------------------------------------
# _format_entry_md
# ---------------------------------------------------------------------------

class TestFormatEntryMd:
    def test_added_with_type(self):
        entry = ChangeEntry(
            action="added", short_id="abc123",
            details=["type: some protein (GO:0001234)", "contributor: Val Wood"],
        )
        lines = _format_entry_md(entry)
        assert any("**Added**" in l for l in lines)
        assert any("`abc123`" in l for l in lines)
        assert any("some protein (GO:0001234)" in l for l in lines)
        # type: should not appear as a sub-bullet
        assert not any(l.strip().startswith("- type:") for l in lines)
        # contributor should appear as a sub-bullet
        assert any("contributor: Val Wood" in l for l in lines)

    def test_added_without_type_uses_id(self):
        entry = ChangeEntry(action="added", short_id="abc123", details=[])
        lines = _format_entry_md(entry)
        # Falls back to short_id as label
        assert any("abc123" in l and "**Added**" in l for l in lines)

    def test_removed_with_type(self):
        entry = ChangeEntry(
            action="removed", short_id="def456",
            details=["type: evidence (ECO:0000303)"],
        )
        lines = _format_entry_md(entry)
        assert len(lines) == 1
        assert "**Removed**" in lines[0]
        assert "`def456`" in lines[0]
        assert "evidence (ECO:0000303)" in lines[0]

    def test_removed_without_type(self):
        entry = ChangeEntry(action="removed", short_id="def456", details=[])
        lines = _format_entry_md(entry)
        assert "**Removed**" in lines[0]
        assert "def456" in lines[0]

    def test_changed_with_arrow(self):
        entry = ChangeEntry(
            action="changed", short_id="ghi789",
            details=["type: old label (GO:0001)  →  new label (GO:0002)"],
        )
        lines = _format_entry_md(entry)
        assert any("**Changed**" in l for l in lines)
        assert any("type:" in l and "→" in l for l in lines)

    def test_changed_with_added_detail(self):
        entry = ChangeEntry(
            action="changed", short_id="ghi789",
            details=["+ occurs_in: ind999"],
        )
        lines = _format_entry_md(entry)
        assert any("added occurs_in: ind999" in l for l in lines)

    def test_changed_with_removed_detail(self):
        entry = ChangeEntry(
            action="changed", short_id="ghi789",
            details=["- enabled_by: ind888"],
        )
        lines = _format_entry_md(entry)
        assert any("removed enabled_by: ind888" in l for l in lines)

    def test_changed_with_plain_detail(self):
        entry = ChangeEntry(
            action="changed", short_id="ghi789",
            details=["something unexpected"],
        )
        lines = _format_entry_md(entry)
        assert any("something unexpected" in l for l in lines)


# ---------------------------------------------------------------------------
# _summarize_diff
# ---------------------------------------------------------------------------

class TestSummarizeDiff:
    def test_all_zero(self):
        d = VersionDiff(old_ts="a", new_ts="b")
        assert _summarize_diff(d) == "no semantic changes"

    def test_added_only(self):
        d = VersionDiff(old_ts="a", new_ts="b", added=3)
        assert _summarize_diff(d) == "+3 added"

    def test_removed_only(self):
        d = VersionDiff(old_ts="a", new_ts="b", removed=2)
        assert _summarize_diff(d) == "-2 removed"

    def test_modified_only(self):
        d = VersionDiff(old_ts="a", new_ts="b", modified=1)
        assert _summarize_diff(d) == "~1 modified"

    def test_mixed(self):
        d = VersionDiff(old_ts="a", new_ts="b", added=5, removed=3, modified=2)
        result = _summarize_diff(d)
        assert "+5 added" in result
        assert "-3 removed" in result
        assert "~2 modified" in result


# ---------------------------------------------------------------------------
# generate_changelog_md
# ---------------------------------------------------------------------------

class TestGenerateChangelogMd:
    def test_title_with_model_id(self):
        md = generate_changelog_md([], model_id="test123")
        assert "# Changelog: Model test123" in md

    def test_title_without_model_id(self):
        md = generate_changelog_md([])
        assert "# Changelog: Model\n" in md

    def test_empty_diffs_no_crash(self):
        md = generate_changelog_md([])
        assert "**0 snapshots**" in md
        assert "**0 diffs**" in md

    def test_summary_stats(self):
        diffs = parse_changes(SAMPLE_INPUT)
        md = generate_changelog_md(diffs)
        assert "**4 snapshots**" in md
        assert "**3 diffs**" in md
        assert "**+3** added" in md
        assert "**-0** removed" in md
        assert "**~2** modified" in md

    def test_date_range(self):
        diffs = parse_changes(SAMPLE_INPUT)
        md = generate_changelog_md(diffs)
        assert "2026-02-12 to 2026-02-20" in md

    def test_date_headers(self):
        diffs = parse_changes(SAMPLE_INPUT)
        md = generate_changelog_md(diffs)
        assert "## 2026-02-12" in md
        assert "## 2026-02-20" in md

    def test_axiom_only_date_message(self):
        diffs = parse_changes(SAMPLE_INPUT)
        md = generate_changelog_md(diffs)
        idx_12 = md.index("## 2026-02-12")
        idx_20 = md.index("## 2026-02-20")
        section = md[idx_12:idx_20]
        assert "No semantic changes" in section

    def test_day_edit_session_count(self):
        diffs = parse_changes(SAMPLE_INPUT)
        md = generate_changelog_md(diffs)
        # Feb 20 has 2 substantive diffs (the cross-date one + the additions one)
        assert "edit session" in md

    def test_time_range_headers(self):
        diffs = parse_changes(SAMPLE_INPUT)
        md = generate_changelog_md(diffs)
        assert "### " in md

    def test_italic_summary_per_session(self):
        diffs = parse_changes(SAMPLE_INPUT)
        md = generate_changelog_md(diffs)
        # Each session has an italic summary line
        assert "_~2 modified_" in md
        assert "_+3 added_" in md

    def test_axiom_only_sessions_skipped_within_day(self):
        """Axiom-only sessions within a substantive day should be silently skipped."""
        text = """\
======================================================================
  2026-03-01_10-00-00  →  2026-03-01_10-05-00
======================================================================
  +0 individuals added, -0 removed, ~0 modified
  (axiom annotation / blank node reordering only)

======================================================================
  2026-03-01_10-05-00  →  2026-03-01_11-00-00
======================================================================
  +1 individuals added, -0 removed, ~0 modified

  + ADDED  ind1
           type: something
"""
        diffs = parse_changes(text)
        md = generate_changelog_md(diffs)
        # The axiom-only session should not get a ### heading
        assert md.count("### ") == 1

    def test_added_entries_present(self):
        diffs = parse_changes(SAMPLE_INPUT)
        md = generate_changelog_md(diffs)
        assert "**Added**" in md
        assert "`6994852c00002749`" in md

    def test_changed_entries_present(self):
        diffs = parse_changes(SAMPLE_INPUT)
        md = generate_changelog_md(diffs)
        assert "**Changed**" in md
        assert "`693b3c0900004188`" in md

    def test_collapsible_removed_over_3(self):
        diffs = parse_changes(REMOVALS_INPUT)
        md = generate_changelog_md(diffs)
        assert "<details>" in md
        assert "5 individuals removed" in md
        assert "</details>" in md

    def test_collapsible_removed_shows_type(self):
        diffs = parse_changes(REMOVALS_INPUT)
        md = generate_changelog_md(diffs)
        assert "author statement (ECO:0000303)" in md

    def test_no_collapsible_for_3_or_fewer(self):
        text = """\
======================================================================
  2026-03-01_10-00-00  →  2026-03-01_11-00-00
======================================================================
  +0 individuals added, -2 removed, ~0 modified

  - REMOVED  x1
             type: something
  - REMOVED  x2
             type: something
"""
        diffs = parse_changes(text)
        md = generate_changelog_md(diffs)
        assert "<details>" not in md

    def test_collapsible_added_same_type(self):
        text = """\
======================================================================
  2026-03-01_10-00-00  →  2026-03-01_11-00-00
======================================================================
  +4 individuals added, -0 removed, ~0 modified

  + ADDED  a1
           type: same type
  + ADDED  a2
           type: same type
  + ADDED  a3
           type: same type
  + ADDED  a4
           type: same type
"""
        diffs = parse_changes(text)
        md = generate_changelog_md(diffs)
        assert "<details>" in md
        assert "4 individuals added (same type)" in md

    def test_no_collapsible_added_mixed_types(self):
        text = """\
======================================================================
  2026-03-01_10-00-00  →  2026-03-01_11-00-00
======================================================================
  +4 individuals added, -0 removed, ~0 modified

  + ADDED  a1
           type: type A
  + ADDED  a2
           type: type B
  + ADDED  a3
           type: type A
  + ADDED  a4
           type: type B
"""
        diffs = parse_changes(text)
        md = generate_changelog_md(diffs)
        # Mixed types: no collapsible, all inline
        assert "<details>" not in md

    def test_collapsible_removed_mixed_types_no_type_note(self):
        diffs = parse_changes(MIXED_TYPES_REMOVED_INPUT)
        md = generate_changelog_md(diffs)
        # 4 removed with mixed types — should still collapse but without type note
        assert "<details>" in md
        assert "4 individuals removed</summary>" in md

    def test_multiple_dates_ordered(self):
        diffs = parse_changes(MULTI_DATE_INPUT)
        md = generate_changelog_md(diffs)
        idx_10 = md.index("## 2026-02-10")
        idx_11 = md.index("## 2026-02-11")
        idx_12 = md.index("## 2026-02-12")
        assert idx_10 < idx_11 < idx_12

    def test_horizontal_rules_between_dates(self):
        diffs = parse_changes(MULTI_DATE_INPUT)
        md = generate_changelog_md(diffs)
        assert md.count("---") >= 3

    def test_removed_entries_in_markdown(self):
        diffs = parse_changes(REMOVALS_INPUT)
        md = generate_changelog_md(diffs)
        assert "**Removed**" in md

    def test_changed_added_relationship_in_markdown(self):
        diffs = parse_changes(REMOVALS_INPUT)
        md = generate_changelog_md(diffs)
        assert "added directly_provides_input_for:" in md


# ---------------------------------------------------------------------------
# generate_changelog (end-to-end file I/O)
# ---------------------------------------------------------------------------

class TestGenerateChangelog:
    def test_writes_file(self, tmp_path):
        input_path = tmp_path / "changes_human.log"
        input_path.write_text(SAMPLE_INPUT, encoding="utf-8")
        output_path = tmp_path / "changelog.md"

        stats = generate_changelog(str(input_path), str(output_path), model_id="test")
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "# Changelog: Model test" in content

    def test_stats_diffs_parsed(self, tmp_path):
        input_path = tmp_path / "changes_human.log"
        input_path.write_text(SAMPLE_INPUT, encoding="utf-8")
        output_path = tmp_path / "changelog.md"

        stats = generate_changelog(str(input_path), str(output_path))
        assert stats.diffs_parsed == 3

    def test_stats_dates(self, tmp_path):
        input_path = tmp_path / "changes_human.log"
        input_path.write_text(SAMPLE_INPUT, encoding="utf-8")
        output_path = tmp_path / "changelog.md"

        stats = generate_changelog(str(input_path), str(output_path))
        assert stats.dates == 2  # 2026-02-12 and 2026-02-20

    def test_stats_total_changes(self, tmp_path):
        input_path = tmp_path / "changes_human.log"
        input_path.write_text(SAMPLE_INPUT, encoding="utf-8")
        output_path = tmp_path / "changelog.md"

        stats = generate_changelog(str(input_path), str(output_path))
        assert stats.total_changes == 5  # 3 added + 2 modified

    def test_empty_input(self, tmp_path):
        input_path = tmp_path / "changes_human.log"
        input_path.write_text("", encoding="utf-8")
        output_path = tmp_path / "changelog.md"

        stats = generate_changelog(str(input_path), str(output_path))
        assert stats.diffs_parsed == 0
        assert stats.dates == 0
        assert stats.total_changes == 0
        assert output_path.exists()

    def test_model_id_in_output(self, tmp_path):
        input_path = tmp_path / "changes_human.log"
        input_path.write_text(SAMPLE_INPUT, encoding="utf-8")
        output_path = tmp_path / "changelog.md"

        generate_changelog(str(input_path), str(output_path), model_id="693b3c0900004140")
        content = output_path.read_text(encoding="utf-8")
        assert "693b3c0900004140" in content

    def test_multi_date_stats(self, tmp_path):
        input_path = tmp_path / "changes_human.log"
        input_path.write_text(MULTI_DATE_INPUT, encoding="utf-8")
        output_path = tmp_path / "changelog.md"

        stats = generate_changelog(str(input_path), str(output_path))
        assert stats.diffs_parsed == 3
        assert stats.dates == 3
        assert stats.total_changes == 2  # 1 added + 1 removed

    def test_output_is_valid_markdown(self, tmp_path):
        """Basic structural check: headings, no unclosed tags."""
        input_path = tmp_path / "changes_human.log"
        input_path.write_text(REMOVALS_INPUT, encoding="utf-8")
        output_path = tmp_path / "changelog.md"

        generate_changelog(str(input_path), str(output_path))
        content = output_path.read_text(encoding="utf-8")

        assert content.startswith("# ")
        assert content.count("<details>") == content.count("</details>")
        assert content.count("<summary>") == content.count("</summary>")
