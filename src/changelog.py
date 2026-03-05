"""Generate a markdown changelog from the semantic diff output.

Parses ``changes_human.log`` (produced by ``diff_versions.py``) and
produces a curator-friendly markdown document grouped by date, with
summary statistics and collapsible detail sections.

Usage::

    python src/changelog.py <changes_human_log> [-o OUTPUT]

Example::

    python src/changelog.py downloads/diffs/changes_human.log
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ChangeEntry:
    """A single added / removed / changed individual."""

    action: str  # "added", "removed", "changed"
    short_id: str
    details: list[str] = field(default_factory=list)


@dataclass
class VersionDiff:
    """One diff block between two timestamps."""

    old_ts: str
    new_ts: str
    added: int = 0
    removed: int = 0
    modified: int = 0
    axiom_only: bool = False
    entries: list[ChangeEntry] = field(default_factory=list)

    @property
    def date(self) -> str:
        """Extract date (YYYY-MM-DD) from the new_ts."""
        return self.new_ts[:10].replace("_", "-")

    @property
    def old_time(self) -> str:
        return self.old_ts[11:].replace("-", ":")

    @property
    def new_time(self) -> str:
        return self.new_ts[11:].replace("-", ":")

    @property
    def is_empty(self) -> bool:
        return self.added == 0 and self.removed == 0 and self.modified == 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r"^\s+(\S+)\s+→\s+(\S+)\s*$")
_SUMMARY_RE = re.compile(
    r"^\s+\+(\d+) individuals added, -(\d+) removed, ~(\d+) modified"
)
_ADDED_RE = re.compile(r"^\s+\+ ADDED\s+(\S+)")
_REMOVED_RE = re.compile(r"^\s+- REMOVED\s+(\S+)")
_CHANGED_RE = re.compile(r"^\s+~ CHANGED\s+(\S+)")
_DETAIL_RE = re.compile(r"^\s{8,}(.+)$")


def parse_changes(text: str) -> list[VersionDiff]:
    """Parse the changes_human.log text into structured diffs."""
    diffs: list[VersionDiff] = []
    current: VersionDiff | None = None
    current_entry: ChangeEntry | None = None

    for line in text.splitlines():
        if line.startswith("="):
            continue

        m = _HEADER_RE.match(line)
        if m:
            if current is not None:
                if current_entry:
                    current.entries.append(current_entry)
                diffs.append(current)
            current = VersionDiff(old_ts=m.group(1), new_ts=m.group(2))
            current_entry = None
            continue

        if current is None:
            continue

        m = _SUMMARY_RE.match(line)
        if m:
            current.added = int(m.group(1))
            current.removed = int(m.group(2))
            current.modified = int(m.group(3))
            continue

        if "axiom annotation" in line:
            current.axiom_only = True
            continue

        m = _ADDED_RE.match(line)
        if m:
            if current_entry:
                current.entries.append(current_entry)
            current_entry = ChangeEntry(action="added", short_id=m.group(1))
            continue

        m = _REMOVED_RE.match(line)
        if m:
            if current_entry:
                current.entries.append(current_entry)
            current_entry = ChangeEntry(action="removed", short_id=m.group(1))
            continue

        m = _CHANGED_RE.match(line)
        if m:
            if current_entry:
                current.entries.append(current_entry)
            current_entry = ChangeEntry(action="changed", short_id=m.group(1))
            continue

        m = _DETAIL_RE.match(line)
        if m and current_entry:
            current_entry.details.append(m.group(1).strip())

    if current is not None:
        if current_entry:
            current.entries.append(current_entry)
        diffs.append(current)

    return diffs


# ---------------------------------------------------------------------------
# Markdown generator
# ---------------------------------------------------------------------------

def _format_entry_md(entry: ChangeEntry) -> list[str]:
    """Format one individual change as markdown lines."""
    lines = []
    type_detail = ""
    for d in entry.details:
        if d.startswith("type:"):
            type_detail = d[5:].strip()
            break

    if entry.action == "added":
        label = type_detail or entry.short_id
        lines.append(f"  - **Added** `{entry.short_id}` — {label}")
        for d in entry.details:
            if d.startswith("type:"):
                continue
            lines.append(f"    - {d}")
    elif entry.action == "removed":
        label = type_detail or entry.short_id
        lines.append(f"  - **Removed** `{entry.short_id}` — {label}")
    elif entry.action == "changed":
        lines.append(f"  - **Changed** `{entry.short_id}`")
        for d in entry.details:
            if "→" in d:
                key, _, rest = d.partition(":")
                lines.append(f"    - {key.strip()}: {rest.strip()}")
            elif d.startswith("+ "):
                lines.append(f"    - added {d[2:]}")
            elif d.startswith("- "):
                lines.append(f"    - removed {d[2:]}")
            else:
                lines.append(f"    - {d}")
    return lines


def _summarize_diff(diff: VersionDiff) -> str:
    """One-line summary of a diff block."""
    parts = []
    if diff.added:
        parts.append(f"+{diff.added} added")
    if diff.removed:
        parts.append(f"-{diff.removed} removed")
    if diff.modified:
        parts.append(f"~{diff.modified} modified")
    return ", ".join(parts) if parts else "no semantic changes"


def generate_changelog_md(diffs: list[VersionDiff], model_id: str = "") -> str:
    """Produce markdown text from parsed diffs."""
    lines: list[str] = []

    # Header
    title = f"Model {model_id}" if model_id else "Model"
    lines.append(f"# Changelog: {title}")
    lines.append("")

    # Summary counts
    total_added = sum(d.added for d in diffs)
    total_removed = sum(d.removed for d in diffs)
    total_modified = sum(d.modified for d in diffs)
    n_snapshots = len(diffs) + 1 if diffs else 0
    date_range = ""
    if diffs:
        first_date = diffs[0].old_ts[:10].replace("_", "-")
        last_date = diffs[-1].new_ts[:10].replace("_", "-")
        date_range = f"{first_date} to {last_date}"

    lines.append(f"> **{n_snapshots} snapshots** across **{len(diffs)} diffs** "
                 f"({date_range})")
    lines.append(f"> Totals: **+{total_added}** added, "
                 f"**-{total_removed}** removed, "
                 f"**~{total_modified}** modified individuals")
    lines.append("")

    # Group by date
    by_date: dict[str, list[VersionDiff]] = {}
    for d in diffs:
        by_date.setdefault(d.date, []).append(d)

    for date, day_diffs in by_date.items():
        lines.append(f"---")
        lines.append("")
        lines.append(f"## {date}")
        lines.append("")

        # Day summary
        day_added = sum(d.added for d in day_diffs)
        day_removed = sum(d.removed for d in day_diffs)
        day_modified = sum(d.modified for d in day_diffs)
        substantive = [d for d in day_diffs if not d.is_empty]

        if not substantive:
            lines.append("*No semantic changes (axiom/blank node reordering only).*")
            lines.append("")
            continue

        lines.append(f"**{len(substantive)} edit session{'s' if len(substantive) != 1 else ''}** "
                     f"— +{day_added} added, -{day_removed} removed, ~{day_modified} modified")
        lines.append("")

        for diff in day_diffs:
            if diff.is_empty and diff.axiom_only:
                continue  # skip noise

            lines.append(f"### {diff.old_time} → {diff.new_time}")
            lines.append("")
            lines.append(f"_{_summarize_diff(diff)}_")
            lines.append("")

            if not diff.entries:
                continue

            # Group entries by action for cleaner display
            added = [e for e in diff.entries if e.action == "added"]
            removed = [e for e in diff.entries if e.action == "removed"]
            changed = [e for e in diff.entries if e.action == "changed"]

            # Collapse large groups of similar entries
            if added:
                if len(added) > 3:
                    # Check if all same type
                    types = set()
                    for e in added:
                        for d in e.details:
                            if d.startswith("type:"):
                                types.add(d[5:].strip())
                    if len(types) == 1:
                        lines.append(f"<details><summary>{len(added)} individuals added "
                                     f"({types.pop()})</summary>")
                        lines.append("")
                        for e in added:
                            lines.extend(_format_entry_md(e))
                        lines.append("")
                        lines.append("</details>")
                        lines.append("")
                    else:
                        for e in added:
                            lines.extend(_format_entry_md(e))
                else:
                    for e in added:
                        lines.extend(_format_entry_md(e))

            if removed:
                if len(removed) > 3:
                    types = set()
                    for e in removed:
                        for d in e.details:
                            if d.startswith("type:"):
                                types.add(d[5:].strip())
                    type_note = f" ({types.pop()})" if len(types) == 1 else ""
                    lines.append(f"<details><summary>{len(removed)} individuals removed"
                                 f"{type_note}</summary>")
                    lines.append("")
                    for e in removed:
                        lines.extend(_format_entry_md(e))
                    lines.append("")
                    lines.append("</details>")
                    lines.append("")
                else:
                    for e in removed:
                        lines.extend(_format_entry_md(e))

            if changed:
                for e in changed:
                    lines.extend(_format_entry_md(e))

            lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

@dataclass
class ChangelogStats:
    """Counts for changelog generation."""

    diffs_parsed: int = 0
    dates: int = 0
    total_changes: int = 0

    def __str__(self) -> str:
        return (
            f"{self.diffs_parsed} diffs parsed across {self.dates} dates, "
            f"{self.total_changes} individual changes."
        )


def generate_changelog(changes_path: str, output_path: str,
                       model_id: str = "") -> ChangelogStats:
    """Read changes_human.log and write a markdown changelog.

    Returns stats about what was generated.
    """
    text = Path(changes_path).read_text(encoding="utf-8")
    diffs = parse_changes(text)

    md = generate_changelog_md(diffs, model_id=model_id)
    Path(output_path).write_text(md, encoding="utf-8")

    by_date = {}
    for d in diffs:
        by_date.setdefault(d.date, []).append(d)

    return ChangelogStats(
        diffs_parsed=len(diffs),
        dates=len(by_date),
        total_changes=sum(d.added + d.removed + d.modified for d in diffs),
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a markdown changelog from changes_human.log.",
    )
    parser.add_argument("file", help="Path to changes_human.log.")
    parser.add_argument(
        "-o", "--output",
        help="Output markdown path (default: changelog.md next to input).",
    )
    parser.add_argument(
        "-m", "--model",
        default="",
        help="Model ID to include in the title.",
    )
    args = parser.parse_args()

    inpath = Path(args.file)
    output = args.output or str(inpath.with_name("changelog.md"))

    stats = generate_changelog(args.file, output, model_id=args.model)
    print(f"Done. {stats}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
