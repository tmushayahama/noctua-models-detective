# Task: Modular pipeline refactor

**Status:** COMPLETE
**Branch:** main

## Goal

Refactor pipeline from monolithic class-with-methods into a properly modular step-based architecture. Each step is its own class, modes are just lists of steps, shared state flows through a context object.

## Context

- **Related files:** `src/pipeline.py`, `src/steps.py`
- **Triggered by:** Previous refactor was just functions wrapped in a class — not truly modular

## Architecture

```
PipelineContext (dataclass)     — shared state bag (paths, config, intermediate outputs)
    |
Step classes (in steps.py)      — each has `name` + `run(ctx)`, imports lazily
    |
Mode presets (FULL / LOG_ONLY / REPO_ONLY) — plain lists of step instances
    |
Pipeline (in pipeline.py)      — iterates steps, prints progress, that's it
    |
CLI (in pipeline.py)           — argparse, auto-detects mode via Pipeline.from_args()
```

## Steps Done

### Phase 1: Create `src/steps.py`
- [x] `PipelineContext` dataclass with input config + intermediate output slots
- [x] 9 step classes: `CleanStep`, `FilterStep`, `ResolveOntologyStep`, `ResolveMetadataStep`, `HumanizeStep`, `ExtractVersionsStep`, `ResolveOntologyTtlStep`, `DiffStep`, `ReportStep`
- [x] 3 mode presets: `FULL_STEPS`, `LOG_ONLY_STEPS`, `REPO_ONLY_STEPS`

### Phase 2: Rewrite `src/pipeline.py`
- [x] `Pipeline` class: just `__init__(ctx, steps)` + `run()` loop
- [x] `Pipeline.from_args()` factory: builds context, picks step list
- [x] CLI unchanged (same args, same `--help` output)

### Phase 3: Clean up imports
- [x] Remove all `try/except ImportError` dual-import hacks from `clean.py`, `humanize.py`, `diff_versions.py`, `report.py`
- [x] Use direct `from src.X import Y` everywhere

### Phase 4: Verify
- [x] `python -c "from src.pipeline import Pipeline"` — OK
- [x] `python -m src.pipeline --help` — same output as before

## Summary

- `pipeline.py`: 100 lines (was 250). Just Pipeline + CLI, no business logic.
- `steps.py`: 130 lines. All step logic, context, and mode presets.
- Adding/removing/reordering steps = editing a list, not touching orchestration.
- No dual-import hacks anywhere in the codebase.

## Files Modified

| File | Action | Status |
| ---- | ------ | ------ |
| `src/steps.py` | New — step classes, context, mode presets | Done |
| `src/pipeline.py` | Rewrite — thin Pipeline + CLI | Done |
| `src/clean.py` | Fix imports | Done |
| `src/humanize.py` | Fix imports | Done |
| `src/diff_versions.py` | Fix imports | Done |
| `src/report.py` | Fix imports | Done |
