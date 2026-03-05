"""Generate semantic diffs between consecutive TTL version snapshots.

Parses TTL individuals from each version, compares them, and produces a
human-readable changelog showing only meaningful changes: added/removed
individuals, type changes, relationship changes, and annotation edits.

Ignores blank nodes, class/property declarations, and axiom annotation
reorderings.

Usage::

    python src/diff_versions.py <versions_dir> [-o OUTPUT_DIR]

Example::

    python src/diff_versions.py downloads/models -o downloads/diffs
"""

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class DiffStats:
    """Counts for a diff-generation run."""

    versions_found: int = 0
    diffs_written: int = 0
    identical_skipped: int = 0

    def __str__(self) -> str:
        return (
            f"{self.versions_found} versions found, "
            f"{self.diffs_written} diffs written, "
            f"{self.identical_skipped} identical pairs skipped."
        )


# ---------------------------------------------------------------------------
# URI shortener
# ---------------------------------------------------------------------------

class Uri:
    """Shorten common OBO/GO/OWL URIs into readable labels."""

    _PATTERNS = [
        (re.compile(r"http://purl\.obolibrary\.org/obo/GO_(\d+)"), r"GO:\1"),
        (re.compile(r"http://purl\.obolibrary\.org/obo/ECO_(\d+)"), r"ECO:\1"),
        (re.compile(r"http://purl\.obolibrary\.org/obo/BFO_0000066"), "occurs_in"),
        (re.compile(r"http://purl\.obolibrary\.org/obo/BFO_0000050"), "part_of"),
        (re.compile(r"http://purl\.obolibrary\.org/obo/RO_0002333"), "enabled_by"),
        (re.compile(r"http://purl\.obolibrary\.org/obo/RO_0002413"), "directly_provides_input_for"),
        (re.compile(r"http://purl\.obolibrary\.org/obo/RO_0002233"), "has_input"),
        (re.compile(r"http://purl\.obolibrary\.org/obo/RO_0002630"), "directly_negatively_regulates"),
        (re.compile(r"http://purl\.obolibrary\.org/obo/RO_0012009"), "constitutively_upstream_of"),
        (re.compile(r"http://purl\.obolibrary\.org/obo/(\w+)"), r"obo:\1"),
        (re.compile(r"http://identifiers\.org/(\w+)/(\S+)"), r"\1:\2"),
        (re.compile(r"http://model\.geneontology\.org/[^/]+/(\S+)"), r"\1"),
        (re.compile(r"http://model\.geneontology\.org/(\S+)"), r"model:\1"),
    ]

    @classmethod
    def shorten(cls, uri: str) -> str:
        for pattern, repl in cls._PATTERNS:
            result = pattern.sub(repl, uri)
            if result != uri:
                return result
        return uri


# ---------------------------------------------------------------------------
# TTL individual parser
# ---------------------------------------------------------------------------

@dataclass
class Individual:
    """A parsed NamedIndividual from TTL."""

    uri: str
    short_id: str
    types: list[str] = field(default_factory=list)
    relationships: dict[str, list[str]] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    raw_lines: list[str] = field(default_factory=list)

    def type_label(self) -> str:
        """Return the meaningful type (GO/ECO term, gene product), skipping NamedIndividual."""
        for t in self.types:
            if "NamedIndividual" not in t:
                return Uri.shorten(t)
        return "NamedIndividual"


_SUBJECT_RE = re.compile(r"^<(http://model\.geneontology\.org/[^>]+)>\s+(.+)$")
_URI_RE = re.compile(r"<([^>]+)>")
_LITERAL_RE = re.compile(r'"([^"]*)"')
_XSD_STRIP = re.compile(r'\^\^<[^>]+>')


class TtlParser:
    """Lightweight parser that extracts NamedIndividuals from a TTL file.

    Skips blank nodes (_:), class declarations, and property declarations.
    """

    def parse(self, filepath: str) -> dict[str, Individual]:
        """Return a dict of short_id → Individual."""
        individuals: dict[str, Individual] = {}

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        current_subject = None
        current_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("_:"):
                if current_subject and stripped.endswith("."):
                    self._finalize(current_subject, current_lines, individuals)
                    current_subject = None
                    current_lines = []
                continue

            m = _SUBJECT_RE.match(stripped)
            if m:
                # New subject — finalize previous
                if current_subject:
                    self._finalize(current_subject, current_lines, individuals)
                current_subject = m.group(1)
                current_lines = [stripped]
            elif current_subject:
                current_lines.append(stripped)

                if stripped.endswith("."):
                    self._finalize(current_subject, current_lines, individuals)
                    current_subject = None
                    current_lines = []

        if current_subject:
            self._finalize(current_subject, current_lines, individuals)

        return individuals

    def _finalize(self, subject: str, lines: list[str], out: dict[str, Individual]) -> None:
        # Skip the model ontology declaration itself
        if subject.count("/") < 4:
            # e.g. http://model.geneontology.org/693b3c0900004140 (no individual suffix)
            joined = " ".join(lines)
            if "owl#Ontology" in joined:
                return

        short_id = Uri.shorten(subject)
        ind = Individual(uri=subject, short_id=short_id, raw_lines=lines[:])

        # Normalize continuation lines (tab-indented) into single space-joined text
        all_text = " ".join(l.strip() for l in lines)

        # Extract types from "a <...> , <...>"
        type_match = re.search(r"\ba\s+(<[^>]+>(?:\s*,\s*<[^>]+>)*)", all_text)
        if type_match:
            for uri in _URI_RE.findall(type_match.group(1)):
                ind.types.append(uri)

        # Extract relationships (object properties)
        rel_predicates = [
            "BFO_0000066", "BFO_0000050", "RO_0002333", "RO_0002413",
            "RO_0002233", "RO_0002630", "RO_0012009",
        ]
        for pred in rel_predicates:
            pattern = re.compile(rf"<[^>]*{pred}>\s+<([^>]+)>")
            for match in pattern.finditer(all_text):
                pred_short = Uri.shorten(f"http://purl.obolibrary.org/obo/{pred}")
                ind.relationships.setdefault(pred_short, []).append(Uri.shorten(match.group(1)))

        # Extract annotations
        for key, label in [
            ("dc/elements/1.1/contributor", "contributor"),
            ("dc/elements/1.1/date", "date"),
            ("dc/elements/1.1/source", "source"),
            ("pav/providedBy", "providedBy"),
            ("lego/evidence-with", "evidence-with"),
        ]:
            pattern = re.compile(rf"{re.escape(key)}>\s+" + r'"([^"]*)"')
            m = pattern.search(all_text)
            if m:
                ind.annotations[label] = m.group(1)

        out[short_id] = ind


# ---------------------------------------------------------------------------
# Semantic diff builder
# ---------------------------------------------------------------------------

class SemanticDiff:
    """Compare two parsed TTL versions and produce a human-readable changelog."""

    def diff(self, old: dict[str, Individual], new: dict[str, Individual],
             old_name: str, new_name: str, has_raw_diff: bool = True) -> str:
        """Return human-readable diff text (always includes the header)."""
        old_ids = set(old.keys())
        new_ids = set(new.keys())

        added_ids = new_ids - old_ids
        removed_ids = old_ids - new_ids
        common_ids = old_ids & new_ids

        changes: list[str] = []

        # Added individuals
        for sid in sorted(added_ids):
            ind = new[sid]
            changes.append(self._format_added(ind))

        # Removed individuals
        for sid in sorted(removed_ids):
            ind = old[sid]
            changes.append(self._format_removed(ind))

        # Modified individuals
        modified = 0
        for sid in sorted(common_ids):
            diff_text = self._diff_individual(old[sid], new[sid])
            if diff_text:
                changes.append(diff_text)
                modified += 1

        lines = []
        lines.append("=" * 70)
        lines.append(f"  {old_name}  →  {new_name}")
        lines.append("=" * 70)
        lines.append(f"  +{len(added_ids)} individuals added, "
                      f"-{len(removed_ids)} removed, "
                      f"~{modified} modified")

        if not changes and has_raw_diff:
            lines.append("  (axiom annotation / blank node reordering only)")
        lines.append("")
        lines.extend(changes)
        return "\n".join(lines)

    def _format_added(self, ind: Individual) -> str:
        lines = [f"  + ADDED  {ind.short_id}"]
        lines.append(f"           type: {ind.type_label()}")
        for rel, targets in ind.relationships.items():
            for t in targets:
                lines.append(f"           {rel}: {t}")
        for key in ("contributor", "date", "source", "evidence-with", "providedBy"):
            if key in ind.annotations:
                lines.append(f"           {key}: {ind.annotations[key]}")
        return "\n".join(lines)

    def _format_removed(self, ind: Individual) -> str:
        lines = [f"  - REMOVED  {ind.short_id}"]
        lines.append(f"             type: {ind.type_label()}")
        return "\n".join(lines)

    def _diff_individual(self, old: Individual, new: Individual) -> str | None:
        diffs: list[str] = []

        # Type change
        old_type = old.type_label()
        new_type = new.type_label()
        if old_type != new_type:
            diffs.append(f"           type: {old_type}  →  {new_type}")

        # Relationship changes
        all_rels = set(list(old.relationships.keys()) + list(new.relationships.keys()))
        for rel in sorted(all_rels):
            old_targets = set(old.relationships.get(rel, []))
            new_targets = set(new.relationships.get(rel, []))
            for t in sorted(new_targets - old_targets):
                diffs.append(f"           + {rel}: {t}")
            for t in sorted(old_targets - new_targets):
                diffs.append(f"           - {rel}: {t}")

        # Annotation changes
        for key in ("date", "source", "evidence-with", "contributor", "providedBy"):
            old_val = old.annotations.get(key)
            new_val = new.annotations.get(key)
            if old_val != new_val:
                if old_val and new_val:
                    diffs.append(f"           {key}: {old_val}  →  {new_val}")
                elif new_val:
                    diffs.append(f"           + {key}: {new_val}")
                else:
                    diffs.append(f"           - {key}: {old_val}")

        if not diffs:
            return None

        header = f"  ~ CHANGED  {old.short_id}"
        return header + "\n" + "\n".join(diffs)


# ---------------------------------------------------------------------------
# Differ (orchestrator)
# ---------------------------------------------------------------------------

class VersionDiffer:
    """Compare consecutive TTL snapshots and produce diffs."""

    def __init__(self, versions_dir: str, output_dir: str):
        self._versions_dir = Path(versions_dir)
        self._output_dir = Path(output_dir)

    def _find_versions(self) -> list[tuple[str, Path]]:
        """Find all version subfolders and their TTL files, sorted by timestamp."""
        results = []
        for folder in sorted(self._versions_dir.iterdir()):
            if not folder.is_dir():
                continue
            ttl_files = list(folder.glob("*.ttl"))
            if ttl_files:
                results.append((folder.name, ttl_files[0]))
        return results

    def _load_lines(self, path: Path) -> list[str]:
        return path.read_text(encoding="utf-8").splitlines(keepends=True)

    def diff_all(self) -> DiffStats:
        """Generate diffs for all consecutive version pairs."""
        self._output_dir.mkdir(parents=True, exist_ok=True)
        stats = DiffStats()
        parser = TtlParser()
        semantic = SemanticDiff()

        versions = self._find_versions()
        stats.versions_found = len(versions)

        all_human: list[str] = []

        for i in range(len(versions) - 1):
            old_ts, old_path = versions[i]
            new_ts, new_path = versions[i + 1]

            old_lines = self._load_lines(old_path)
            new_lines = self._load_lines(new_path)

            diff = list(difflib.unified_diff(
                old_lines, new_lines,
                fromfile=f"{old_ts}/{old_path.name}",
                tofile=f"{new_ts}/{new_path.name}",
            ))

            if not diff:
                stats.identical_skipped += 1
                continue

            # Raw unified diff
            diff_name = f"diff_{i + 1:02d}_{old_ts}_to_{new_ts}.diff"
            diff_path = self._output_dir / diff_name
            with open(diff_path, "w", encoding="utf-8") as f:
                f.writelines(diff)

            # Semantic human-readable diff
            old_inds = parser.parse(str(old_path))
            new_inds = parser.parse(str(new_path))
            human_text = semantic.diff(old_inds, new_inds, old_ts, new_ts)
            all_human.append(human_text)

            stats.diffs_written += 1

        # Write combined human-readable changelog
        if all_human:
            human_path = self._output_dir / "changes_human.log"
            with open(human_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(all_human) + "\n")

        return stats


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def diff_versions(versions_dir: str, output_dir: str) -> DiffStats:
    """Generate diffs between consecutive TTL versions."""
    differ = VersionDiffer(versions_dir, output_dir)
    return differ.diff_all()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate diffs between consecutive TTL version snapshots.",
    )
    parser.add_argument("versions_dir", help="Directory containing timestamped TTL subfolders.")
    parser.add_argument(
        "-o", "--output",
        help="Output directory for diffs (default: <versions_dir>/diffs).",
    )
    args = parser.parse_args()

    outdir = args.output or str(Path(args.versions_dir) / "diffs")
    stats = diff_versions(args.versions_dir, outdir)
    print(f"Done. {stats}")
    print(f"Output: {outdir}")


if __name__ == "__main__":
    main()
