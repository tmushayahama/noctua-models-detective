# Task: Generate analysis report from cleaned barista/minerva logs

**Status:** COMPLETE
**Issue:** N/A
**Branch:** N/A

## Goal

Parse cleaned log files and produce a comprehensive report covering API usage, HTTP traffic, performance, errors, and traffic patterns.

## Context

- **Related files:** `src/report.py`, `src/common.py`, `src/clean.py` (prerequisite)
- **Triggered by:** User request — extract useful insights from barista/minerva server logs
- **Prerequisite:** Run `src/clean.py` first (see `.plans/misc/log-cleanup.md`)

## Steps

### Phase 1: Clean the log (prerequisite)

- [x] Run `python src/clean.py hold.log/hold.log`

### Phase 2: Generate report

- [x] Run `python src/report.py hold.log/hold.log`
- [x] Report saved to `hold.log/hold_report.txt`

### Phase 3: Review findings

- [x] Check report output for actionable insights

## Architecture

### Classes

- `AnsiStripper` (shared via `common.py`) — strips ANSI escape codes
- `ApiCall` — dataclass for barista API proxy call records
- `HttpRequest` — dataclass for Express HTTP access log records
- `ParsedLog` — container for all parsed records
- `LogParser` — parses cleaned log files using regex into `ParsedLog`
- `ReportBuilder` — builds a text report from `ParsedLog`

### Log formats parsed

```
# API proxy call (barista) — with timestamp
barista [2026-02-17T15:19:47.216Z]:  api xlate (GET): [http://toaster.lbl.gov:6800]/search/taxa

# HTTP access log (Express with ANSI codes) — with response time
GET /search/taxa 200 7355.270 ms - 5115
^method  ^path    ^status ^time_ms   ^size

# POST body data (barista) — counted, not deeply parsed
barista [2026-02-17T15:24:00.227Z]:  Received body data: intention=query&...
```

### Report sections

| Section              | Source     | Content                                 |
| -------------------- | ---------- | --------------------------------------- |
| Overview             | Both       | Total counts, date range                |
| API methods          | api xlate  | GET vs POST breakdown                   |
| Top API endpoints    | api xlate  | Most-called backend paths               |
| Daily volume         | api xlate  | Requests per date                       |
| Busiest hours        | api xlate  | Top 15 hours with visual bars           |
| HTTP methods         | Access log | GET/POST/PUT/DELETE/HEAD breakdown      |
| Status codes         | Access log | 200/302/etc distribution                |
| Top HTTP endpoints   | Access log | Most-hit URL paths                      |
| Response time stats  | Access log | Min, median, P95, P99, max              |
| Slowest requests     | Access log | Top 15 individual slow calls            |
| Errors               | Access log | 4xx/5xx grouped by status+endpoint      |
| Avg latency/endpoint | Access log | Slowest endpoints by mean response time |

### Key findings from Feb 17-26 data

- `/m3BatchPrivileged` is the dominant endpoint (13K+ calls, 37% of all traffic)
- Slowest requests: `m3Batch` calls hitting 35-82 seconds
- P95 response time: ~3s, P99: ~9.3s
- Traffic spike: Feb 25 at 19:00 (3K+ requests in one hour)
- 10 unique backend API endpoints

## Recovery Checkpoint

> TASK COMPLETE

- **Last completed action:** Report script rewritten with classes and full docs
- **Recent commands run:**
  - `python src/report.py hold.log/hold.log`

## Files Modified

| File                       | Action                                 | Status |
| -------------------------- | -------------------------------------- | ------ |
| `src/common.py`            | Shared `AnsiStripper` utility          | Done   |
| `src/report.py`            | Analysis report generator with classes | Done   |
| `hold.log/hold_report.txt` | Generated report output                | Done   |

## Summary

Built a log analysis pipeline: `clean.py` strips noise/secrets, `report.py` generates a text report with traffic volume, endpoint usage, response time percentiles, slowest requests, error breakdown, and hourly traffic patterns. Python stdlib only — no external dependencies.

## Lessons Learned

- Express/Morgan logs embed ANSI color codes — must strip before regex parsing
- Two distinct log formats coexist in the same file (barista timestamped + Express access log)
- Bot scanner traffic (now removed by clean.py) was 10K+ lines of 404 noise

## Additional Context

Potential future enhancements:

- CSV/JSON export for spreadsheets or dashboards
- Parse `Received body data:` to analyze model operations (get/store/add/remove)
- User activity tracking via ORCID contributor IDs in search queries
- Detect anomalous response times or error spikes
- Compare traffic across date ranges
