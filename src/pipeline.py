#!/usr/bin/env python3
"""GO Noctua model analysis pipeline.

Supports three usage modes depending on available inputs:

Full pipeline (log + model repo)::

    python -m src.pipeline -f logs/hold.log -o downloads/ \\
        -m 693b3c0900004140 -r C:/work/go/noctua-models-temp --after 2026-02-01

Log only (no repo)::

    python -m src.pipeline -f logs/hold.log -o downloads/ -m 693b3c0900004140

Repo only (no log file)::

    python -m src.pipeline -o downloads/ -m 693b3c0900004140 \\
        -r C:/work/go/noctua-models-temp --after 2026-02-01
"""

import argparse
from pathlib import Path

from src.steps import (
    PipelineContext,
    FULL_STEPS,
    LOG_ONLY_STEPS,
    REPO_ONLY_STEPS,
)


class Pipeline:
    """Runs a sequence of steps against a shared context."""

    def __init__(self, ctx: PipelineContext, steps: list):
        self._ctx = ctx
        self._steps = steps

    def run(self) -> None:
        self._ctx.output_dir.mkdir(parents=True, exist_ok=True)
        total = len(self._steps)
        for i, step in enumerate(self._steps, 1):
            print(f"[{i}/{total}] {step.name} ...")
            step.run(self._ctx)
        print("\nDone.")

    @classmethod
    def from_args(
        cls,
        output_dir: str,
        model_id: str,
        log_file: str | None = None,
        repo_path: str | None = None,
        after: str | None = None,
    ) -> "Pipeline":
        """Auto-detect mode and return a configured Pipeline."""
        ctx = PipelineContext(
            output_dir=Path(output_dir),
            model_id=model_id,
            log_file=Path(log_file) if log_file else None,
            repo_path=repo_path,
            after=after,
        )

        if log_file and repo_path:
            steps = FULL_STEPS
        elif log_file:
            steps = LOG_ONLY_STEPS
        elif repo_path:
            steps = REPO_ONLY_STEPS
        else:
            raise ValueError("Must provide at least --file or --repo.")

        return cls(ctx, steps)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="GO Noctua model analysis pipeline.",
        epilog="""\
Usage modes:
  Full (log + repo):  python -m src.pipeline -f log.log -o out/ -m MODEL -r REPO [--after DATE]
  Log only:           python -m src.pipeline -f log.log -o out/ -m MODEL
  Repo only:          python -m src.pipeline -o out/ -m MODEL -r REPO [--after DATE]
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-f", "--file", help="Path to the raw barista log file.")
    parser.add_argument("-o", "--outdir", required=True, help="Output directory.")
    parser.add_argument(
        "-m", "--model", required=True,
        help="GO model ID (e.g. 693b3c0900004140).",
    )
    parser.add_argument("-r", "--repo", help="Path to noctua-models git repo.")
    parser.add_argument(
        "--after",
        help="Only extract TTL versions after this date (e.g. 2026-02-01).",
    )
    args = parser.parse_args()

    if not args.file and not args.repo:
        parser.error("Must provide at least --file or --repo.")

    pipeline = Pipeline.from_args(
        output_dir=args.outdir,
        model_id=args.model,
        log_file=args.file,
        repo_path=args.repo,
        after=args.after,
    )
    pipeline.run()


if __name__ == "__main__":
    main()
