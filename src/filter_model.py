"""Filter a cleaned barista log to keep only lines for a specific GO model.

Useful for isolating all operations (queries, edits, stores) performed
on a single model, e.g. ``gomodel:693b3c0900004140``.

Prerequisite: run ``clean.py`` first.

Usage::

    python src/filter_model.py <clean_logfile> <model_id>

Example::

    python src/filter_model.py output/hold_clean.log 693b3c0900004140
"""

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

@dataclass
class FilterStats:
    """Counts of lines processed during a model-filter run."""

    total_lines: int = 0
    kept: int = 0

    def __str__(self) -> str:
        return (
            f"{self.kept:,} lines matched "
            f"(from {self.total_lines:,} total)."
        )


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------

class ModelFilter:
    """Keeps only log lines that mention a given model ID.

    The match is a plain substring check — the model ID appears in URLs,
    query strings, and POST body payloads, so a simple ``in`` test is
    sufficient and fast.
    """

    def __init__(self, model_id: str):
        self._model_id = model_id

    def matches(self, line: str) -> bool:
        """Return ``True`` if *line* references the model."""
        return self._model_id in line


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def filter_by_model(
    input_path: str,
    model_id: str,
    output_path: str,
) -> FilterStats:
    """Filter *input_path* keeping only lines that mention *model_id*.

    Writes matching lines to *output_path* and returns statistics.
    """
    mf = ModelFilter(model_id)
    stats = FilterStats()

    with open(input_path, "r", encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:
        for line in fin:
            stats.total_lines += 1
            if mf.matches(line):
                fout.write(line)
                stats.kept += 1

    return stats


def main() -> None:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Filter a cleaned log to a single GO model.",
    )
    parser.add_argument("file", help="Path to the cleaned log file.")
    parser.add_argument("model_id", help="Model ID to filter for (e.g. 693b3c0900004140).")
    parser.add_argument(
        "-o", "--output",
        help="Output path (default: <stem>_<model_id>.log next to input).",
    )
    args = parser.parse_args()

    inpath = Path(args.file)
    output = args.output or str(inpath.with_name(f"{inpath.stem}_{args.model_id}.log"))

    stats = filter_by_model(args.file, args.model_id, output)
    print(f"Done. {stats}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
