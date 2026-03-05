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
    from src.diff_versions import diff_versions
    from src.extract_versions import extract_versions
    from src.filter_model import filter_by_model
    from src.humanize import humanize
    from src.report import generate_report
except ImportError:
    from clean import clean_file
    from diff_versions import diff_versions
    from extract_versions import extract_versions
    from filter_model import filter_by_model
    from humanize import humanize
    from report import generate_report


def run(
    input_file: str,
    output_dir: str,
    model_id: str | None = None,
    repo_path: str | None = None,
    after: str | None = None,
) -> None:
    """Run the full clean + filter + report pipeline."""
    inpath = Path(input_file)
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    stem = inpath.stem
    clean_path = outdir / f"{stem}_clean.log"

    has_model = model_id is not None
    has_repo = has_model and repo_path is not None
    steps = 1 + (3 if has_model else 0) + (2 if has_repo else 0) + 1
    step = 0

    # Step: Clean
    step += 1
    print(f"[{step}/{steps}] Cleaning {inpath} ...")
    stats = clean_file(str(inpath), str(clean_path))
    print(f"       {stats}")
    print(f"       Cleaned log: {clean_path}")

    # Step: Filter by model
    report_source = clean_path
    if has_model:
        filtered_path = outdir / f"{stem}_clean_{model_id}.log"
        step += 1
        print(f"[{step}/{steps}] Filtering for model {model_id} ...")
        fstats = filter_by_model(str(clean_path), model_id, str(filtered_path))
        print(f"       {fstats}")
        print(f"       Filtered log: {filtered_path}")
        report_source = filtered_path

        # Step: Humanize
        human_path = outdir / f"{stem}_clean_{model_id}_human.log"
        step += 1
        print(f"[{step}/{steps}] Humanizing operations log ...")
        hcount = humanize(str(filtered_path), str(human_path))
        print(f"       {hcount} entries formatted.")
        print(f"       Human log: {human_path}")

        # Step: Extract TTL versions from git
        if has_repo:
            models_dir = outdir / "models"
            step += 1
            print(f"[{step}/{steps}] Extracting TTL versions from git ...")
            estats = extract_versions(repo_path, model_id, str(models_dir), after=after)
            print(f"       {estats}")
            print(f"       Models dir: {models_dir}")

            # Step: Diff consecutive versions
            diffs_dir = outdir / "diffs"
            step += 1
            print(f"[{step}/{steps}] Generating diffs between versions ...")
            dstats = diff_versions(str(models_dir / "by_folder"), str(diffs_dir))
            print(f"       {dstats}")
            print(f"       Diffs dir: {diffs_dir}")

    # Step: Report
    report_path = outdir / f"{report_source.stem}_report.txt"
    step += 1
    print(f"[{step}/{steps}] Generating report ...")
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
    parser.add_argument(
        "-r", "--repo",
        help="Path to noctua-models git repo (enables TTL version extraction).",
    )
    parser.add_argument(
        "--after",
        help="Only extract TTL versions after this date (e.g. 2026-02-01).",
    )
    args = parser.parse_args()

    run(args.file, args.outdir, model_id=args.model,
        repo_path=args.repo, after=args.after)


if __name__ == "__main__":
    main()
