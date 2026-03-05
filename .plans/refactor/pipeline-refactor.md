# Task: Refactor pipeline.py into Pipeline class with 3 usage modes

**Status:** COMPLETE
**Branch:** main

## Goal

Refactor `pipeline.py` from monolithic `run()` into a `Pipeline` class with 3 modes (full, log-only, repo-only). Update CLI, README, and docstrings.

## Context

- **Related files:** `src/pipeline.py`, `README.md`
- **Triggered by:** User request to professionalize the pipeline

## Steps

### Phase 1: Rewrite `src/pipeline.py`

- [x] `Pipeline` class with `__init__(output_dir, model_id, log_file=None, repo_path=None, after=None)`
- [x] Shared `_labels` dict for ontology cache; `_step`/`_total_steps` counter; `_log()` helper
- [x] Private step methods: `_step_clean`, `_step_filter`, `_step_resolve_ontology`, `_step_metadata`, `_step_humanize`, `_step_extract`, `_step_resolve_ontology_ttl`, `_step_diff`, `_step_report`
- [x] Three public methods: `run_full()` (9 steps), `run_log_only()` (6 steps), `run_repo_only()` (4 steps), `run()` (auto-detect)
- [x] New CLI with named args: `-f/--file`, `-o/--outdir`, `-m/--model`, `-r/--repo`, `--after`
- [x] Validation: at least `--file` or `--repo` required
- [x] Module docstring with 3 usage examples

### Phase 2: Update `README.md`

- [x] Pipeline diagram showing 3 modes
- [x] "Usage modes" section with examples
- [x] Add pyyaml to requirements
- [x] Document caches (ontology_cache.json, metadata_cache.json)
- [x] Update project structure tree with all modules
- [x] Add entries for new modules

### Phase 3: Verify

- [x] Test repo-only: `python -m src.pipeline -o downloads/ -m 693b3c0900004140 -r C:/work/go/noctua-models-temp --after 2026-02-01`
- [x] Test `--help` output

## Recovery Checkpoint

> ✅ TASK COMPLETE

## Summary

- Rewrote `pipeline.py` with a `Pipeline` class (3 public run methods, 9 private step helpers, ~190 lines)
- CLI changed from positional to named args, log file now optional
- README updated with full docs: 3 usage modes, all modules, caches, project structure
- Repo-only mode tested and working

## Files Modified

| File | Action | Status |
| ---- | ------ | ------ |
| `src/pipeline.py` | Rewrite with Pipeline class | Done |
| `README.md` | Update with 3 modes, new modules | Done |
| `.plans/refactor/pipeline-refactor.md` | Plan file | Done |
