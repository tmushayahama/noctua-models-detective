# Barista/Minerva Log Analysis

Tools for cleaning and analysing [Barista](http://berkeleybop.org/barista/) server logs from the [Gene Ontology Noctua](http://noctua.geneontology.org/) platform.

## Overview

Raw barista logs mix useful API traffic with large amounts of noise — token entities, OAuth secrets, heartbeat pings, static asset requests, vulnerability scanner probes, and ANSI colour codes. This toolkit strips all of that, then generates a traffic analysis report from what remains.

### Pipeline

```text
raw log  ──>  clean.py  ──>  cleaned log  ──>  report.py  ──>  report.txt
```

## Requirements

- Python 3.10+
- No external dependencies (stdlib only)

## Quick start

```bash
# 1. Clean the log (removes secrets, tokens, noise)
python src/clean.py hold.log/hold.log

# 2. Generate the analysis report
python src/report.py hold.log/hold.log
# Report printed to stdout and saved to hold.log/hold_report.txt
```

## src

### `src/clean.py`

Cleans a raw barista log file **in-place**. Safe to run multiple times (idempotent).

**What it removes:**

| Category                 | Examples                                                             |
| ------------------------ | -------------------------------------------------------------------- |
| Token entity blocks      | `{ token: '...', uri: '...', ... }` multi-line objects               |
| GitHub OAuth secrets     | `secrets for github { clientID: '...', clientSecret: '...' }`        |
| Token values in URLs     | `token=abc123&` and `barista_token=xyz&` redacted from query strings |
| Barista internal chatter | Heartbeats, broadcasts, session lookups, disconnect messages         |
| Static assets            | `.js`, `.css`, `.ico`, `.png`, `.jpg`, `.gif`, `.svg`, fonts         |
| Auth flow                | `/login`, `/auth/`, GitHub OAuth callback messages                   |
| All HTTP 404s            | Scanner bots probing `/wp-admin`, `/cgi-bin/`, `/index.php`, etc.    |
| Non-API paths            | `/status`, `/logout`, `/users/`, `/groups/`, `/robots.txt`           |
| Startup config           | `Express server listening`, `Barista location`, token config         |

**Architecture:**

- `AnsiStripper` (shared in `common.py`) — strips ANSI escape codes before matching
- `BlockFilter` — removes multi-line `{}` blocks using brace-depth tracking
- `LineFilter` — removes single lines matching noise regex patterns
- `TokenRedactor` — redacts token values from URL query strings
- `CleanStats` — reports removal counts

**Example output:**

```text
Done. Removed 120,000 lines. 51,555 lines remain (from 171,555 total).
```

### `src/report.py`

Parses a **cleaned** log file and generates a text analysis report.

**Two log formats are parsed:**

```text
# barista API proxy call (timestamped)
barista [2026-02-17T15:19:47.216Z]:  api xlate (GET): [http://toaster.lbl.gov:6800]/search/taxa

# Express HTTP access log (with ANSI codes, response time, size)
GET /search/taxa 200 7355.270 ms - 5115
```

**Report sections:**

| Section          | Description                                                  |
| ---------------- | ------------------------------------------------------------ |
| Overview         | Total counts, date range                                     |
| API proxy calls  | Method breakdown, top endpoints, daily volume, busiest hours |
| HTTP access log  | Method/status breakdown, top endpoints                       |
| Response time    | Min, median, P95, P99, max percentiles                       |
| Slowest requests | Top 15 individual slow calls                                 |
| Errors           | 4xx/5xx grouped by status and endpoint                       |
| Avg latency      | Per-endpoint average response time, ranked                   |

**Architecture:**

- `LogParser` — regex-based parser producing `ApiCall`, `HttpRequest`, `ParsedLog` dataclasses
- `ReportBuilder` — constructs the text report from parsed data

**Example output:**

```text
======================================================================
BARISTA LOG ANALYSIS REPORT
======================================================================

Source: hold.log/hold.log
API proxy calls (api xlate): 21,433
HTTP access log entries:     21,433
POST body data entries:      8,169
Date range: 2026-02-17 to 2026-02-26

----------------------------------------------------------------------
API PROXY CALLS (api xlate)
----------------------------------------------------------------------

Top endpoints (10 unique):
    13,199  /m3BatchPrivileged
     4,148  /search/models
     3,305  /m3Batch
       ...

Response time (ms):
  Min:             0.2
  Median:         60.9
  P95:         2,990.4
  P99:         9,259.9
  Max:        82,253.1
```

### `src/common.py`

Shared utilities used by both src.

- `AnsiStripper` — removes ANSI escape codes (`\x1b[...m`) from log lines

## Project structure

```text
val_analysis/
  src/
    __init__.py       # Package init
    common.py         # Shared utilities (AnsiStripper)
    clean.py          # Log cleaning script
    report.py         # Log analysis report generator
  hold.log/
    hold.log          # Raw or cleaned log file
    hold_report.txt   # Generated report
  .plans/
    misc/
      log-cleanup.md  # Cleanup task plan
      log-analysis.md # Analysis task plan
    template.md       # Plan template
  README.md           # This file
```

## Plans

Task plans are in `.plans/misc/`:

- [log-cleanup.md](.plans/misc/log-cleanup.md) — documents all noise patterns, failed approaches, and lessons learned from building `clean.py`
- [log-analysis.md](.plans/misc/log-analysis.md) — documents report sections, log formats, key findings, and future enhancement ideas
