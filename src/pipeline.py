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

try:
    from src.clean import clean_file
    from src.diff_versions import diff_versions
    from src.extract_versions import extract_versions
    from src.filter_model import filter_by_model
    from src.humanize import humanize
    from src.report import generate_report
    from src.resolve_metadata import load_cache as load_meta_cache, refresh_cache as refresh_meta
    from src.resolve_ontology import load_cache, collect_ids_from_files, resolve, save_cache
except ImportError:
    from clean import clean_file
    from diff_versions import diff_versions
    from extract_versions import extract_versions
    from filter_model import filter_by_model
    from humanize import humanize
    from report import generate_report
    from resolve_metadata import load_cache as load_meta_cache, refresh_cache as refresh_meta
    from resolve_ontology import load_cache, collect_ids_from_files, resolve, save_cache


class Pipeline:
    """GO model analysis pipeline with three execution modes."""

    def __init__(
        self,
        output_dir: str,
        model_id: str,
        log_file: str | None = None,
        repo_path: str | None = None,
        after: str | None = None,
    ):
        self._outdir = Path(output_dir)
        self._model_id = model_id
        self._log_file = Path(log_file) if log_file else None
        self._repo_path = repo_path
        self._after = after
        self._step = 0
        self._total_steps = 0
        self._labels: dict[str, str] = {}

    def _log(self, message: str) -> None:
        self._step += 1
        print(f"[{self._step}/{self._total_steps}] {message}")

    def _info(self, message: str) -> None:
        print(f"       {message}")

    # ------------------------------------------------------------------
    # Step helpers
    # ------------------------------------------------------------------

    def _step_clean(self) -> Path:
        stem = self._log_file.stem
        clean_path = self._outdir / f"{stem}_clean.log"
        self._log(f"Cleaning {self._log_file} ...")
        stats = clean_file(str(self._log_file), str(clean_path))
        self._info(str(stats))
        self._info(f"Cleaned log: {clean_path}")
        return clean_path

    def _step_filter(self, clean_path: Path) -> Path:
        stem = self._log_file.stem
        filtered_path = self._outdir / f"{stem}_clean_{self._model_id}.log"
        self._log(f"Filtering for model {self._model_id} ...")
        fstats = filter_by_model(str(clean_path), self._model_id, str(filtered_path))
        self._info(str(fstats))
        self._info(f"Filtered log: {filtered_path}")
        return filtered_path

    def _step_resolve_ontology(self, files: list[str]) -> None:
        self._log("Resolving ontology labels ...")
        if not self._labels:
            self._labels = load_cache()
        ids = collect_ids_from_files(files)
        n = resolve(ids, self._labels)
        save_cache(self._labels)
        self._info(f"{n} new labels resolved ({len(self._labels)} cached).")

    def _step_resolve_ontology_ttl(self, models_dir: Path) -> None:
        self._log("Resolving ontology labels from TTL files ...")
        if not self._labels:
            self._labels = load_cache()
        ttl_files = [str(p) for p in (models_dir / "by_folder").rglob("*.ttl")]
        ids = collect_ids_from_files(ttl_files)
        n = resolve(ids, self._labels)
        save_cache(self._labels)
        self._info(f"{n} new labels resolved ({len(self._labels)} cached).")

    def _step_metadata(self) -> None:
        meta = load_meta_cache()
        if meta.get("users") and meta.get("groups"):
            self._log(
                f"Contributor & group metadata cached "
                f"({len(meta['users'])} users, {len(meta['groups'])} groups)."
            )
        else:
            self._log("Fetching contributor & group metadata ...")
            refresh_meta()

    def _step_humanize(self, filtered_path: Path) -> None:
        stem = self._log_file.stem
        human_path = self._outdir / f"{stem}_clean_{self._model_id}_human.log"
        self._log("Humanizing operations log ...")
        hcount = humanize(str(filtered_path), str(human_path))
        self._info(f"{hcount} entries formatted.")
        self._info(f"Human log: {human_path}")

    def _step_extract(self) -> Path:
        models_dir = self._outdir / "models"
        self._log("Extracting TTL versions from git ...")
        estats = extract_versions(
            self._repo_path, self._model_id, str(models_dir), after=self._after,
        )
        self._info(str(estats))
        self._info(f"Models dir: {models_dir}")
        return models_dir

    def _step_diff(self, models_dir: Path) -> None:
        diffs_dir = self._outdir / "diffs"
        self._log("Generating diffs between versions ...")
        dstats = diff_versions(str(models_dir / "by_folder"), str(diffs_dir))
        self._info(str(dstats))
        self._info(f"Diffs dir: {diffs_dir}")

    def _step_report(self, source_path: Path) -> None:
        report_path = self._outdir / f"{source_path.stem}_report.txt"
        self._log("Generating report ...")
        generate_report(str(source_path), str(report_path))
        self._info(f"Report: {report_path}")

    # ------------------------------------------------------------------
    # Public run methods
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Auto-detect mode and run the appropriate pipeline."""
        self._outdir.mkdir(parents=True, exist_ok=True)

        has_log = self._log_file is not None
        has_repo = self._repo_path is not None

        if has_log and has_repo:
            self.run_full()
        elif has_log:
            self.run_log_only()
        elif has_repo:
            self.run_repo_only()
        else:
            raise ValueError("Must provide at least --file or --repo.")

        print("\nDone.")

    def run_full(self) -> None:
        """Full pipeline: log + repo (9 steps)."""
        self._total_steps = 9
        clean_path = self._step_clean()
        filtered_path = self._step_filter(clean_path)
        self._step_resolve_ontology([str(filtered_path)])
        self._step_metadata()
        self._step_humanize(filtered_path)
        models_dir = self._step_extract()
        self._step_resolve_ontology_ttl(models_dir)
        self._step_diff(models_dir)
        self._step_report(filtered_path)

    def run_log_only(self) -> None:
        """Log only: no repo (6 steps)."""
        self._total_steps = 6
        clean_path = self._step_clean()
        filtered_path = self._step_filter(clean_path)
        self._step_resolve_ontology([str(filtered_path)])
        self._step_metadata()
        self._step_humanize(filtered_path)
        self._step_report(filtered_path)

    def run_repo_only(self) -> None:
        """Repo only: no log file (4 steps)."""
        self._total_steps = 4
        self._step_metadata()
        models_dir = self._step_extract()
        self._step_resolve_ontology_ttl(models_dir)
        self._step_diff(models_dir)


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

    pipeline = Pipeline(
        output_dir=args.outdir,
        model_id=args.model,
        log_file=args.file,
        repo_path=args.repo,
        after=args.after,
    )
    pipeline.run()


if __name__ == "__main__":
    main()
