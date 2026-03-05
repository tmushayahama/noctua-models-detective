# Task: Improve diff output and ontology cache resilience

**Status:** ACTIVE
**Branch:** main

## Goal
Enhance the repo-only pipeline output with: (1) wire `changelog.py` into the pipeline as a step, (2) fix unresolved ontology IDs, (3) handle "axiom-only" diffs better, and (4) optionally support non-consecutive version diffing.

## Context
- **Related files:** `src/changelog.py`, `src/diff_versions.py`, `src/resolve_ontology.py`, `src/steps.py`
- **Triggered by:** reviewing `changes_human.log` output and spotting gaps

## Current State
- What works now:
  - Consecutive semantic diffs with resolved labels in `changes_human.log`
  - Unified `.diff` files for each version pair
  - Ontology cache resolves most IDs via EBI OLS4 API
  - `src/changelog.py` fully implemented AND wired into pipeline via `ChangelogStep` in `steps.py`
  - `ChangelogStep` in both `FULL_STEPS` and `REPO_ONLY_STEPS`
  - Cache miss handling: `_resolve_missing_ids()` in `diff_versions.py` resolves IDs created by `Uri.shorten()` before writing output
- What's broken/missing:
  - 4 of 11 diffs are "axiom annotation / blank node reordering only" with no detail
  - Can only diff consecutive versions, not arbitrary pairs (e.g. first vs last)

## Steps

### Phase 1: Wire changelog into pipeline
- [x] `ChangelogStep` already exists in `src/steps.py:144-155`
- [x] Already in `REPO_ONLY_STEPS` and `FULL_STEPS`
- [x] Passes `model_id` from context
- [x] Tests already include it
- **DONE** -- was already implemented before this plan was created

### Phase 2: Ontology cache miss handling
- [x] Root cause: `Uri.shorten()` converts URI underscores (`GO_0140378`) to colon form (`GO:0140378`) during diffing, creating IDs that were never resolved by `ResolveOntologyTtlStep` (which scans raw TTL text for colon-form IDs only found in annotation strings)
- [x] Fix: added `VersionDiffer._resolve_missing_ids()` in `diff_versions.py` -- scans the assembled diff text for unresolved IDs, resolves them via OLS, updates cache, all before `substitute_ontology_labels()` runs
- [x] Tests: 3 new tests in `test_diff_versions.py::TestResolveMissingIds` (resolves missing, skips cached, no save when nothing resolved)
- [x] All 161 tests passing
- **DONE**

### Phase 3: Axiom-only diff detail (optional)
- [ ] For diffs that show "(axiom annotation / blank node reordering only)", consider showing which individuals had their axiom annotations reordered
- [ ] Or: suppress these diffs entirely from the changelog if no semantic content changed
- [ ] Decide which approach is more useful

### Phase 4: Non-consecutive diffing (optional)
- [ ] Add a way to diff any two chosen snapshots (e.g. first vs last)
- [ ] Could be a separate CLI flag like `--net-diff` or `--compare first last`
- [ ] Produces a single "net changes" summary

## Recovery Checkpoint

> **UPDATE THIS AFTER EVERY CHANGE**

- **Last completed action:** Phase 2 done -- added `_resolve_missing_ids()` to `VersionDiffer` + 3 tests
- **Next immediate action:** Discuss Phases 3/4 with user, or commit current changes
- **Recent commands run:** `python -m pytest -v` (161 passed)
- **Uncommitted changes:** `src/diff_versions.py`, `tests/test_diff_versions.py`, `.plans/feature/diff-improvements.md`
- **Environment state:** clean except uncommitted changes above

## Failed Approaches

| What was tried | Why it failed | Date |
| -------------- | ------------- | ---- |
|                |               |      |

## Files Modified

| File | Action | Status |
| ---- | ------ | ------ |
| `src/diff_versions.py` | Added `_resolve_missing_ids()` static method + call in `diff_all()` | Done |
| `tests/test_diff_versions.py` | Added `TestResolveMissingIds` class (3 tests) | Done |

## Blockers
- None currently

## Notes
- Phases 3 and 4 are optional, worth discussing before implementing

## Lessons Learned
- Always check existing code before planning -- `ChangelogStep` was already fully implemented
- TTL files store IDs as URIs with underscores (`GO_0140378`), but the ontology regex only matches colon form (`GO:0140378`). The `Uri.shorten()` step creates these colon-form IDs, so any resolve step running before diffing won't catch them.
