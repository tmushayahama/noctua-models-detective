"""Pipeline steps and shared context for the GO model analysis pipeline.

Each step is a small class with a ``name`` and a ``run(ctx)`` method.
The pipeline composes steps into ordered lists — adding, removing, or
reordering steps means editing a list, not touching orchestration code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Shared context — passed through all steps
# ---------------------------------------------------------------------------

@dataclass
class PipelineContext:
    """Mutable bag of state shared across pipeline steps."""

    output_dir: Path
    model_id: str
    log_file: Path | None = None
    repo_path: str | None = None
    after: str | None = None

    # Intermediate outputs (populated by steps as they run)
    clean_path: Path | None = None
    filtered_path: Path | None = None
    models_dir: Path | None = None
    labels: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

class CleanStep:
    name = "Clean log file"

    def run(self, ctx: PipelineContext) -> None:
        from src.clean import clean_file

        stem = ctx.log_file.stem
        ctx.clean_path = ctx.output_dir / f"{stem}_clean.log"
        stats = clean_file(str(ctx.log_file), str(ctx.clean_path))
        print(f"       {stats}")
        print(f"       Cleaned log: {ctx.clean_path}")


class FilterStep:
    name = "Filter by model"

    def run(self, ctx: PipelineContext) -> None:
        from src.filter_model import filter_by_model

        stem = ctx.log_file.stem
        ctx.filtered_path = ctx.output_dir / f"{stem}_clean_{ctx.model_id}.log"
        stats = filter_by_model(str(ctx.clean_path), ctx.model_id, str(ctx.filtered_path))
        print(f"       {stats}")
        print(f"       Filtered log: {ctx.filtered_path}")


class ResolveOntologyStep:
    name = "Resolve ontology labels"

    def run(self, ctx: PipelineContext) -> None:
        from src.resolve_ontology import load_cache, collect_ids_from_files, resolve, save_cache

        if not ctx.labels:
            ctx.labels = load_cache()
        ids = collect_ids_from_files([str(ctx.filtered_path)])
        n = resolve(ids, ctx.labels)
        save_cache(ctx.labels)
        print(f"       {n} new labels resolved ({len(ctx.labels)} cached).")


class ResolveMetadataStep:
    name = "Resolve contributor metadata"

    def run(self, ctx: PipelineContext) -> None:
        from src.resolve_metadata import load_cache, refresh_cache

        meta = load_cache()
        if meta.get("users") and meta.get("groups"):
            print(f"       Cached ({len(meta['users'])} users, {len(meta['groups'])} groups).")
        else:
            refresh_cache()


class HumanizeStep:
    name = "Humanize operations log"

    def run(self, ctx: PipelineContext) -> None:
        from src.humanize import humanize

        stem = ctx.log_file.stem
        human_path = ctx.output_dir / f"{stem}_clean_{ctx.model_id}_human.log"
        count = humanize(str(ctx.filtered_path), str(human_path))
        print(f"       {count} entries formatted.")
        print(f"       Human log: {human_path}")


class ExtractVersionsStep:
    name = "Extract TTL versions from git"

    def run(self, ctx: PipelineContext) -> None:
        from src.extract_versions import extract_versions

        ctx.models_dir = ctx.output_dir / "models"
        stats = extract_versions(ctx.repo_path, ctx.model_id, str(ctx.models_dir), after=ctx.after)
        print(f"       {stats}")
        print(f"       Models dir: {ctx.models_dir}")


class ResolveOntologyTtlStep:
    name = "Resolve ontology labels (TTL)"

    def run(self, ctx: PipelineContext) -> None:
        from src.resolve_ontology import load_cache, collect_ids_from_files, resolve, save_cache

        if not ctx.labels:
            ctx.labels = load_cache()
        ttl_files = [str(p) for p in (ctx.models_dir / "by_folder").rglob("*.ttl")]
        ids = collect_ids_from_files(ttl_files)
        n = resolve(ids, ctx.labels)
        save_cache(ctx.labels)
        print(f"       {n} new labels resolved ({len(ctx.labels)} cached).")


class DiffStep:
    name = "Generate version diffs"

    def run(self, ctx: PipelineContext) -> None:
        from src.diff_versions import diff_versions

        diffs_dir = ctx.output_dir / "diffs"
        stats = diff_versions(str(ctx.models_dir / "by_folder"), str(diffs_dir))
        print(f"       {stats}")
        print(f"       Diffs dir: {diffs_dir}")


class ReportStep:
    name = "Generate report"

    def run(self, ctx: PipelineContext) -> None:
        from src.report import generate_report

        report_path = ctx.output_dir / f"{ctx.filtered_path.stem}_report.txt"
        generate_report(str(ctx.filtered_path), str(report_path))
        print(f"       Report: {report_path}")


# ---------------------------------------------------------------------------
# Mode presets — each mode is just a list of steps
# ---------------------------------------------------------------------------

FULL_STEPS = [
    CleanStep(),
    FilterStep(),
    ResolveOntologyStep(),
    ResolveMetadataStep(),
    HumanizeStep(),
    ExtractVersionsStep(),
    ResolveOntologyTtlStep(),
    DiffStep(),
    ReportStep(),
]

LOG_ONLY_STEPS = [
    CleanStep(),
    FilterStep(),
    ResolveOntologyStep(),
    ResolveMetadataStep(),
    HumanizeStep(),
    ReportStep(),
]

REPO_ONLY_STEPS = [
    ResolveMetadataStep(),
    ExtractVersionsStep(),
    ResolveOntologyTtlStep(),
    DiffStep(),
]
