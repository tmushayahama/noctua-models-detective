# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GO Noctua model analysis toolkit. Cleans barista/minerva server logs, extracts TTL model versions from git, generates semantic diffs, resolves ontology/metadata labels, and produces traffic reports. All for [Gene Ontology Noctua](http://noctua.geneontology.org/) models.

## Commands

```bash
# Run the full pipeline (log + repo)
python -m src.pipeline -f logs/hold.log -o downloads/ -m MODEL_ID -r /path/to/noctua-models --after 2026-02-01

# Run log-only mode
python -m src.pipeline -f logs/hold.log -o downloads/ -m MODEL_ID

# Run repo-only mode
python -m src.pipeline -o downloads/ -m MODEL_ID -r /path/to/noctua-models --after 2026-02-01

# Run all tests
python -m pytest

# Run a single test file
python -m pytest tests/test_pipeline.py

# Run a single test
python -m pytest tests/test_pipeline.py::TestPipelineContext::test_context_with_all_args

# Install dependencies (Poetry)
poetry install
```

Each module in `src/` can also be run standalone (e.g., `python src/clean.py hold.log`).

## Architecture

**Step-based pipeline** (`src/pipeline.py` + `src/steps.py`):
- `Pipeline` class runs a list of step objects against a shared `PipelineContext` dataclass
- Three mode presets defined as step lists: `FULL_STEPS`, `LOG_ONLY_STEPS`, `REPO_ONLY_STEPS`
- `Pipeline.from_args()` auto-detects mode based on which CLI args are provided
- Steps use lazy imports (inside `run()`) to avoid loading unused dependencies

**Processing flow** (full mode): clean → filter → resolve ontology → resolve metadata → humanize → extract TTL versions → resolve TTL ontology → diff → report

**Key patterns:**
- Each module exposes a top-level function (e.g., `clean_file()`, `filter_by_model()`, `humanize()`) used by both the pipeline step and standalone CLI
- Stats dataclasses with `__str__` for consistent progress output
- Two JSON caches at project root: `ontology_cache.json` (EBI OLS API labels) and `metadata_cache.json` (GitHub go-site contributor/group data)
- External APIs: EBI OLS4 (`resolve_ontology.py`), GitHub raw YAML (`resolve_metadata.py`)
- `diff_versions.py` has a lightweight TTL parser (`TtlParser`) that extracts NamedIndividuals, skipping blank nodes and class/property declarations

## Dependencies

- Python 3.10+
- PyYAML (for metadata resolution)
- pytest (dev)
- Uses Poetry (`pyproject.toml`) with `package-mode = false`

## Conventions

- Do NOT include `Co-Authored-By: Claude` lines in git commits
- Task plans live in `.plans/` directory

## Task Plans

- Always create and maintain task plans using the [.plans/template.md](.plans/template.md) system.
- On context resume, check `.plans/` for ACTIVE plans before doing anything else.