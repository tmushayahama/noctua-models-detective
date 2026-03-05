"""Transform a filtered model log into a human-readable operations log.

Decodes URL-encoded POST payloads, extracts structured operations
(add-type, remove-type, add-annotation, store, etc.), and formats
everything into a clean, readable timeline.

Prerequisite: run ``filter_model.py`` (or ``clean.py``) first.

Usage::

    python src/humanize.py <filtered_logfile> [-o OUTPUT]

Example::

    python src/humanize.py output/hold_clean_693b3c0900004140.log
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, unquote_plus, parse_qs

try:
    from src.common import AnsiStripper
    from src.resolve_metadata import substitute_metadata
except ImportError:
    from common import AnsiStripper
    from resolve_metadata import substitute_metadata


# ---------------------------------------------------------------------------
# Ontology label substitution (reads from pre-built cache, no API calls)
# ---------------------------------------------------------------------------

_ONTOLOGY_PREFIXES = {"GO", "RO", "BFO", "ECO", "SO", "CHEBI", "CL", "UBERON"}
# Matches ontology IDs that are NOT already inside parentheses (i.e. not
# already in "label (ID)" form).  Negative lookbehind for '(' avoids
# double-substitution when the source data already contains labelled IDs.
_ONTOLOGY_ID_RE = re.compile(r"(?<!\()([A-Z]{2,}:\d{5,})\b")
_CACHE_PATH = Path(__file__).resolve().parent.parent / "ontology_cache.json"


def _load_ontology_labels() -> dict[str, str]:
    """Load the ontology label cache (built by ``resolve_ontology.py``)."""
    if _CACHE_PATH.exists():
        try:
            return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def substitute_ontology_labels(text: str) -> str:
    """Replace bare ontology IDs with ``label (ID)`` using the local cache."""
    labels = _load_ontology_labels()
    if not labels:
        return text

    def _repl(m: re.Match) -> str:
        obo_id = m.group(1)
        if obo_id.split(":")[0] not in _ONTOLOGY_PREFIXES:
            return obo_id
        label = labels.get(obo_id)
        return f"{label} ({obo_id})" if label else obo_id

    return _ONTOLOGY_ID_RE.sub(_repl, text)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Operation:
    """A single decoded operation from a barista request batch."""

    entity: str
    operation: str
    arguments: dict = field(default_factory=dict)

    def format(self, indent: str = "    ") -> str:
        """Return a human-readable multi-line representation."""
        lines = [f"{indent}{self.entity}.{self.operation}"]

        args = self.arguments

        # Edge operations: subject --predicate--> object
        if "subject" in args and "predicate" in args and "object" in args:
            subj = args["subject"].rsplit("/", 1)[-1]
            obj = args["object"].rsplit("/", 1)[-1]
            pred = args["predicate"]
            lines.append(f"{indent}  {subj} --{pred}--> {obj}")

        if "individual" in args:
            lines.append(f"{indent}  individual: {args['individual']}")
        if "model-id" in args:
            lines.append(f"{indent}  model: {args['model-id']}")

        if "expressions" in args:
            for expr in args["expressions"]:
                etype = expr.get("type", "?")
                eid = expr.get("id", "?")
                lines.append(f"{indent}  {etype}: {eid}")

        if "values" in args:
            for val in args["values"]:
                key = val.get("key", "?")
                value = unquote_plus(val.get("value", "?"))
                lines.append(f"{indent}  {key}: {value}")

        if "format" in args:
            lines.append(f"{indent}  format: {args['format']}")

        return "\n".join(lines)


@dataclass
class LogEntry:
    """A single parsed log entry, ready for display."""

    timestamp: str
    entry_type: str  # "api", "http", "action", "query"
    summary: str
    operations: list[Operation] = field(default_factory=list)
    details: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

class BodyDataParser:
    """Parse URL-encoded barista POST body data into structured operations."""

    @staticmethod
    def parse(raw_body: str) -> tuple[dict, list[Operation]]:
        """Return (metadata_dict, list_of_operations) from URL-encoded body."""
        params = parse_qs(raw_body, keep_blank_values=True)

        metadata = {}
        for key in ("intention", "use-reasoner", "provided-by"):
            if key in params:
                metadata[key] = params[key][0]

        ops = []
        requests_raw = params.get("requests", [""])[0]
        if requests_raw:
            try:
                requests_json = json.loads(requests_raw)
                for req in requests_json:
                    ops.append(Operation(
                        entity=req.get("entity", "?"),
                        operation=req.get("operation", "?"),
                        arguments=req.get("arguments", {}),
                    ))
            except (json.JSONDecodeError, TypeError):
                pass

        return metadata, ops


class LogEntryParser:
    """Parse a filtered log file into a list of LogEntry objects."""

    _BARISTA_RE = re.compile(
        r"^barista \[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\]:\s+(.+)$"
    )
    _API_XLATE_RE = re.compile(
        r"^api xlate \((\w+)\):\s+\[http://[^\]]+\](/.+)$"
    )
    _BODY_DATA_RE = re.compile(r"^Received body data:\s+(.+)$")
    _HTTP_RE = re.compile(
        r"^(GET|POST|PUT|DELETE|PATCH|HEAD)\s+(\S+)\s+(\d{3})\s+"
        r"([\d.]+)\s+ms\s+-\s+(-|\d+)$"
    )

    def parse(self, filepath: str) -> list[LogEntry]:
        """Read *filepath* and return a list of LogEntry."""
        entries = []

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                clean = AnsiStripper.strip(line.strip())
                entry = self._parse_line(clean)
                if entry:
                    entries.append(entry)

        return entries

    def _parse_line(self, line: str) -> LogEntry | None:
        m = self._BARISTA_RE.match(line)
        if m:
            ts, rest = m.group(1), m.group(2)
            return self._parse_barista(ts, rest)

        m = self._HTTP_RE.match(line)
        if m:
            method, path, status, time_ms, size = m.groups()
            path = unquote(path)
            return LogEntry(
                timestamp="",
                entry_type="http",
                summary=f"{method} {path.split('?')[0]}  -> {status} ({time_ms} ms, {size} bytes)",
                details={"method": method, "path": path, "status": status,
                         "time_ms": time_ms, "size": size},
            )

        return None

    def _parse_barista(self, ts: str, rest: str) -> LogEntry:
        m = self._API_XLATE_RE.match(rest)
        if m:
            method, path = m.group(1), m.group(2)
            base = path.split("?")[0]
            return LogEntry(
                timestamp=ts,
                entry_type="api",
                summary=f"API {method} {base}",
            )

        m = self._BODY_DATA_RE.match(rest)
        if m:
            raw = m.group(1)
            metadata, ops = BodyDataParser.parse(raw)
            intention = metadata.get("intention", "?")
            provider = metadata.get("provided-by", "")
            provider_short = provider.rsplit("/", 1)[-1] if provider else ""

            op_names = [f"{o.entity}.{o.operation}" for o in ops]
            summary_parts = [intention.upper()]
            if provider_short:
                summary_parts.append(f"by {provider_short}")
            summary_parts.append(f"[{', '.join(op_names)}]")

            return LogEntry(
                timestamp=ts,
                entry_type=intention,
                summary=" ".join(summary_parts),
                operations=ops,
                details=metadata,
            )

        return LogEntry(timestamp=ts, entry_type="other", summary=rest)


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

class HumanFormatter:
    """Format a list of LogEntry into a human-readable text report."""

    @staticmethod
    def format(entries: list[LogEntry]) -> str:
        lines = []
        prev_date = ""

        for entry in entries:
            # Date header when day changes
            if entry.timestamp:
                date = entry.timestamp[:10]
                if date != prev_date:
                    if prev_date:
                        lines.append("")
                    lines.append("=" * 70)
                    lines.append(f"  {date}")
                    lines.append("=" * 70)
                    prev_date = date

            # Timestamp (time only)
            time_str = entry.timestamp[11:19] if entry.timestamp else "         "

            # Type tag
            tag = {
                "api": "API  ",
                "http": "HTTP ",
                "action": "EDIT ",
                "query": "QUERY",
            }.get(entry.entry_type, "     ")

            lines.append(f"  {time_str}  [{tag}]  {entry.summary}")

            # Expanded operations for action/query entries
            for op in entry.operations:
                lines.append(op.format(indent="                        "))

        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def humanize(input_path: str, output_path: str) -> int:
    """Transform *input_path* into a human-readable log at *output_path*.

    Returns the number of entries written.
    """
    parser = LogEntryParser()
    entries = parser.parse(input_path)

    text = HumanFormatter.format(entries)
    text = substitute_ontology_labels(text)
    text = substitute_metadata(text)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    return len(entries)


def main() -> None:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Transform a filtered model log into human-readable format.",
    )
    parser.add_argument("file", help="Path to the filtered log file.")
    parser.add_argument(
        "-o", "--output",
        help="Output path (default: <stem>_human.log next to input).",
    )
    args = parser.parse_args()

    inpath = Path(args.file)
    output = args.output or str(inpath.with_name(f"{inpath.stem}_human.log"))

    count = humanize(args.file, output)
    print(f"Done. {count} entries formatted.")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
