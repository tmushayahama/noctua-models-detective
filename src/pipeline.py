#!/usr/bin/env python3
"""End-to-end pipeline: clean a raw barista log and generate an analysis report.

Takes a dirty log file and an output directory, produces a cleaned log and
a text report.

Usage::

    python src/pipeline.py <logfile> <outdir>

Example::

    python src/pipeline.py hold.log/hold.log output/
    # output/hold_clean.log   — cleaned log
    # output/hold_report.txt  — analysis report
"""

import argparse
from pathlib import Path

try:
    from src.clean import clean_file
    from src.filter_model import filter_by_model
    from src.humanize import humanize
    from src.report import generate_report
except ImportError:
    from clean import clean_file
    from filter_model import filter_by_model
    from humanize import humanize
    from report import generate_report


def run(input_file: str, output_dir: str, model_id: str | None = None) -> None:
    """Run the full clean + filter + report pipeline."""
    inpath = Path(input_file)
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    stem = inpath.stem
    clean_path = outdir / f"{stem}_clean.log"

    steps = 4 if model_id else 2

    # Step 1: Clean
    print(f"[1/{steps}] Cleaning {inpath} ...")
    stats = clean_file(str(inpath), str(clean_path))
    print(f"       {stats}")
    print(f"       Cleaned log: {clean_path}")

    # Step 2 (optional): Filter by model
    report_source = clean_path
    if model_id:
        filtered_path = outdir / f"{stem}_clean_{model_id}.log"
        print(f"[2/{steps}] Filtering for model {model_id} ...")
        fstats = filter_by_model(str(clean_path), model_id, str(filtered_path))
        print(f"       {fstats}")
        print(f"       Filtered log: {filtered_path}")
        report_source = filtered_path

        # Step 3: Humanize
        human_path = outdir / f"{stem}_clean_{model_id}_human.log"
        print(f"[3/{steps}] Humanizing operations log ...")
        hcount = humanize(str(filtered_path), str(human_path))
        print(f"       {hcount} entries formatted.")
        print(f"       Human log: {human_path}")

    # Step N: Report
    report_path = outdir / f"{report_source.stem}_report.txt"
    print(f"[{steps}/{steps}] Generating report ...")
    generate_report(str(report_source), str(report_path))
    print(f"       Report: {report_path}")

    print("\nDone.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean a raw barista log and generate an analysis report.",
    )
    parser.add_argument("file", help="Path to the raw (dirty) log file.")
    parser.add_argument("outdir", help="Output directory for cleaned log and report.")
    parser.add_argument(
        "-m", "--model",
        help="Optional model ID to filter for (e.g. 693b3c0900004140).",
    )
    args = parser.parse_args()

    run(args.file, args.outdir, model_id=args.model)


if __name__ == "__main__":
    main()
