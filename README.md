# Barista/Minerva Log Analysis

Tools for cleaning and analysing [Barista](http://berkeleybop.org/barista/) server logs from the [Gene Ontology Noctua](http://noctua.geneontology.org/) platform, and for diffing model TTL versions from [noctua-models](https://github.com/geneontology/noctua-models).

## Overview

Raw barista logs mix useful API traffic with large amounts of noise — token entities, OAuth secrets, heartbeat pings, static asset requests, vulnerability scanner probes, and ANSI colour codes. This toolkit strips all of that, then generates a traffic analysis report from what remains.

The pipeline also extracts TTL file versions from git, generates semantic diffs showing what changed between snapshots, and resolves ontology IDs and contributor/group metadata into human-readable labels.

## Requirements

- Python 3.10+
- [pyyaml](https://pypi.org/project/PyYAML/) (for contributor/group metadata resolution)

## Usage modes

### Full pipeline (log + model repo)

You have a barista log file **and** a noctua-models git repo clone:

```bash
python -m src.pipeline \
    -f logs/hold.log \
    -o downloads/ \
    -m 693b3c0900004140 \
    -r C:/work/go/noctua-models-temp \
    --after 2026-02-01
```

Steps: clean → filter → resolve ontology → resolve metadata → humanize → extract TTL versions → resolve TTL ontology → diff → changelog → report

### Log only (no repo)

You have a barista log file but no git repo:

```bash
python -m src.pipeline \
    -f logs/hold.log \
    -o downloads/ \
    -m 693b3c0900004140
```

Steps: clean → filter → resolve ontology → resolve metadata → humanize → report

### Repo only (no log file)

You have a noctua-models git repo but no log file:

```bash
python -m src.pipeline \
    -o downloads/ \
    -m 693b3c0900004140 \
    -r C:/work/go/noctua-models-temp \
    --after 2026-02-01
```

Steps: resolve metadata → extract TTL versions → resolve TTL ontology → diff → changelog

Example scripts with configurable parameters are in [`scripts/`](scripts/):

- [`run_full.sh`](scripts/run_full.sh) — full pipeline (log + repo)
- [`run_log_only.sh`](scripts/run_log_only.sh) — log only
- [`run_repo_only.sh`](scripts/run_repo_only.sh) — repo only

### CLI reference

```text
python -m src.pipeline [-h] [-f FILE] -o OUTDIR -m MODEL [-r REPO] [--after DATE]

  -f, --file    Path to the raw barista log file (optional)
  -o, --outdir  Output directory (required)
  -m, --model   GO model ID, e.g. 693b3c0900004140 (required)
  -r, --repo    Path to noctua-models git repo (optional)
  --after       Only extract TTL versions after this date, e.g. 2026-02-01
```

## Pipeline steps

| Step | Module | Description |
| ---- | ------ | ----------- |
| Clean | `clean.py` | Remove noise, secrets, tokens from raw barista log |
| Filter | `filter_model.py` | Keep only lines for a specific GO model |
| Resolve ontology | `resolve_ontology.py` | Resolve GO/ECO/RO IDs to labels via EBI OLS API |
| Resolve metadata | `resolve_metadata.py` | Fetch contributor nicknames and group shorthands from GitHub |
| Humanize | `humanize.py` | Transform filtered log into human-readable operations timeline |
| Extract versions | `extract_versions.py` | Extract TTL snapshots from noctua-models git history |
| Diff versions | `diff_versions.py` | Generate semantic diffs between consecutive TTL versions |
| Changelog | `changelog.py` | Convert semantic diffs into a markdown changelog grouped by date |
| Report | `report.py` | Generate traffic analysis report (method breakdown, latency, errors) |

## Standalone scripts

Each module can also be run standalone:

```bash
# Clean a raw log
python src/clean.py hold.log/hold.log

# Filter for a specific model
python src/filter_model.py output/hold_clean.log 693b3c0900004140

# Resolve ontology labels (updates ontology_cache.json)
python src/resolve_ontology.py output/hold_clean_693b3c0900004140.log

# Fetch contributor/group metadata (updates metadata_cache.json)
python src/resolve_metadata.py

# Humanize a filtered log
python src/humanize.py output/hold_clean_693b3c0900004140.log

# Extract TTL versions from git
python src/extract_versions.py C:/work/go/noctua-models-temp 693b3c0900004140 downloads/models --after 2026-02-01

# Diff consecutive TTL versions
python src/diff_versions.py downloads/models/by_folder -o downloads/diffs

# Generate markdown changelog from diffs
python src/changelog.py downloads/diffs/changes_human.log -m 693b3c0900004140

# Generate analysis report
python src/report.py output/hold_clean_693b3c0900004140.log
```

## Caches

The pipeline uses two local JSON caches to avoid repeated network requests:

| Cache | Source | Contents |
| ----- | ------ | -------- |
| `ontology_cache.json` | [EBI OLS4 API](https://www.ebi.ac.uk/ols4/) | GO/ECO/RO/BFO ID → human-readable label |
| `metadata_cache.json` | [geneontology/go-site](https://github.com/geneontology/go-site) | ORCID → contributor nickname, group URL → shorthand |

Caches are created automatically on first run. Delete them to force a refresh. The diff step also resolves any IDs that only appear after URI shortening (e.g. `GO_0140378` in a TTL URI becomes `GO:0140378` in the diff output) and updates the ontology cache automatically.

## Modules

### `src/clean.py`

Cleans a raw barista log file. Safe to run multiple times (idempotent).

**What it removes:**

| Category | Examples |
| -------- | -------- |
| Token entity blocks | `{ token: '...', uri: '...', ... }` multi-line objects |
| GitHub OAuth secrets | `secrets for github { clientID: '...', clientSecret: '...' }` |
| Token values in URLs | `token=abc123&` and `barista_token=xyz&` redacted |
| Barista internal chatter | Heartbeats, broadcasts, session lookups, disconnect messages |
| Static assets | `.js`, `.css`, `.ico`, `.png`, `.jpg`, `.gif`, `.svg`, fonts |
| Auth flow | `/login`, `/auth/`, GitHub OAuth callback messages |
| All HTTP 404s | Scanner bots probing `/wp-admin`, `/cgi-bin/`, etc. |
| Non-API paths | `/status`, `/logout`, `/users/`, `/groups/`, `/robots.txt` |
| Startup config | `Express server listening`, `Barista location`, token config |

**Architecture:** `AnsiStripper` → `BlockFilter` → `LineFilter` → `TokenRedactor`

### `src/filter_model.py`

Filters a cleaned log to keep only lines for a specific GO model ID.

### `src/resolve_ontology.py`

Scans files for OBO ontology IDs (GO, ECO, RO, BFO, etc.) and resolves labels via the EBI OLS4 API. Results cached to `ontology_cache.json`.

### `src/resolve_metadata.py`

Fetches `users.yaml` (contributor ORCID → nickname) and `groups.yaml` (group URL → shorthand) from the geneontology/go-site GitHub repo. Results cached to `metadata_cache.json`.

### `src/humanize.py`

Transforms a filtered model log into a human-readable operations timeline. Applies ontology label and metadata substitution (e.g. `GO:1904600` → `mating projection actin fusion focus assembly (GO:1904600)`).

### `src/extract_versions.py`

Extracts historical TTL file versions from a noctua-models git repo. For each commit that touched the model file, saves the content with a timestamp-based filename (deduplicating identical versions).

### `src/diff_versions.py`

Compares consecutive TTL snapshots and produces a human-readable changelog showing added/removed individuals, type changes, relationship changes, and annotation edits. Applies ontology and metadata label substitution. Automatically resolves any ontology IDs that appear in the diff output but weren't in the pre-built cache (e.g. IDs created by URI shortening during diffing).

### `src/changelog.py`

Converts the plain-text semantic diff output (`changes_human.log`) into a curator-friendly markdown changelog. Groups changes by date with per-session time ranges, summary statistics, and collapsible `<details>` sections for large batches of similar entries (e.g. bulk evidence node removals).

### `src/report.py`

Generates a traffic analysis report from a cleaned log: API usage breakdown, HTTP status codes, response time percentiles, slowest requests, and error summary.

### `src/common.py`

Shared utilities: `AnsiStripper` for removing ANSI escape codes from log lines.

## Project structure

```text
val_analysis/
  src/
    __init__.py            # Package init
    common.py              # Shared utilities (AnsiStripper)
    clean.py               # Log cleaning
    filter_model.py        # Model-specific log filtering
    resolve_ontology.py    # Ontology ID → label resolution (EBI OLS API)
    resolve_metadata.py    # Contributor/group metadata resolution (GitHub)
    humanize.py            # Human-readable operations log formatter
    extract_versions.py    # Git TTL version extractor
    diff_versions.py       # Semantic TTL diff generator
    changelog.py           # Markdown changelog generator
    report.py              # Traffic analysis report generator
    pipeline.py            # Orchestrator (Pipeline class, CLI entry point)
  scripts/
    run_full.sh            # Example: full pipeline (log + repo)
    run_log_only.sh        # Example: log only
    run_repo_only.sh       # Example: repo only
  ontology_cache.json      # Cached ontology labels (auto-generated)
  metadata_cache.json      # Cached contributor/group metadata (auto-generated)
  .plans/
    refactor/
      pipeline-refactor.md # Pipeline refactoring plan
    misc/
      log-cleanup.md       # Cleanup task plan
      log-analysis.md      # Analysis task plan
    template.md            # Plan template
  README.md                # This file
```

## Plans

Task plans are in `.plans/`:

- [pipeline-refactor.md](.plans/refactor/pipeline-refactor.md) — Pipeline class refactoring with 3 usage modes
- [log-cleanup.md](.plans/misc/log-cleanup.md) — documents all noise patterns, failed approaches, and lessons learned from building `clean.py`
- [log-analysis.md](.plans/misc/log-analysis.md) — documents report sections, log formats, key findings, and future enhancement ideas
