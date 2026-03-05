# Task: Clean barista/minerva log files — remove secrets, tokens, and noise

**Status:** COMPLETE
**Issue:** N/A
**Branch:** N/A

## Goal

Clean `hold.log/hold.log` by removing sensitive data (tokens, secrets, credentials) and noise so only meaningful API/HTTP log entries remain for analysis.

## Context

- **Related files:** `src/clean.py`, `src/common.py`, `hold.log/hold.log`
- **Triggered by:** User request — log contains secrets and noise that must be stripped before analysis

## Steps

### Phase 1: Run clean.py

- [x] Place raw log file at `hold.log/hold.log`
- [x] Run `python src/clean.py hold.log/hold.log`
- [x] Verify no secrets/tokens remain

### Phase 2: Verify results

- [x] Spot-check the cleaned file for any remaining noise
- [x] If new noise patterns found, add them to `NOISE_PATTERNS` in `clean.py` and re-run

## What clean.py removes

### Architecture

The script uses four classes plus a shared utility:

- `AnsiStripper` (in `common.py`) — strips ANSI escape codes before pattern matching
- `BlockFilter` — detects multi-line brace-delimited blocks via depth tracking
- `LineFilter` — removes single lines matching noise patterns
- `TokenRedactor` — redacts token values from URL query strings
- `CleanStats` — tracks removal counts

### Sensitive data (BlockFilter + TokenRedactor)

| Pattern                                | Description                                                                      |
| -------------------------------------- | -------------------------------------------------------------------------------- |
| `{ token: '...' }` blocks              | Multi-line token entity objects (all variants: bare, `sess`, `barista`-prefixed) |
| `secrets for github { clientID: ... }` | GitHub OAuth credentials block                                                   |
| `token=xxx&` in URLs                   | Token values in query strings — redacted, line kept                              |

### Noise lines removed (LineFilter)

| Category          | Patterns                                                                                                                                                                                                             |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Barista internal  | `srv disconnect`, `process heartbeat`, `Skip broadcast`, `Broadcast rebuild/merge`, `no token was attempted`, `looks like a token was attempted`, `call using session`, `got user info for`, `respond to query from` |
| Startup/config    | `Barista ...`, `Will ...`, `REPL`, `debug level`, `Express server listening`, token config lines                                                                                                                     |
| Static assets     | `.js`, `.css`, `.ico`, `.png`, `.jpg`, `.gif`, `.svg`, `.woff`, `.ttf`, `.eot`, `.map`                                                                                                                               |
| Health/auth       | `HEAD /status`, `/user_info_by_token/`, `GET /users`, `GET /groups`, `/login`, `/auth/`, GitHub auth flow                                                                                                            |
| All 404 responses | Blanket removal of all HTTP 404 lines (scanner bots, missing pages)                                                                                                                                                  |
| Non-API paths     | `/status`, `/user_info`, `/logout`, `/users/`, `/groups/`, `/robots.txt`, `//`, `/#`, `/`                                                                                                                            |
| Misc              | `undefined`, `Developer (...)`, raw JSON response fragments, stray numeric lines                                                                                                                                     |

### Technical notes

- ANSI codes stripped before all pattern matching
- Multi-line blocks use brace-depth tracking for nested `{}` and `[]`
- `LineFilter` uses `search()` (not `match()`) for flexibility with prefixes
- Idempotent — safe to run multiple times on the same file

## Recovery Checkpoint

> TASK COMPLETE

- **Last completed action:** Final cleanup pass — 51,555 clean lines remain
- **Recent commands run:**
  - `python src/clean.py hold.log/hold.log` (multiple passes, all noise removed)

## Failed Approaches

| What was tried                     | Why it failed                                                 | Date       |
| ---------------------------------- | ------------------------------------------------------------- | ---------- |
| Bash `sed` script                  | Not cross-platform, fragile with multi-line blocks            | 2026-03-04 |
| Matching only `token: '123'`       | Missed other token values (`'000'`, `'6z62'`, session tokens) | 2026-03-04 |
| `NOISE_RE.match()` on raw lines    | ANSI codes prevented `^` anchors from matching                | 2026-03-04 |
| Hardcoded block end patterns       | Broke on varying structures; brace-depth tracking fixed it    | 2026-03-04 |
| Specific scanner bot path patterns | Too many variants; blanket 404 removal was the fix            | 2026-03-04 |

## Files Modified

| File              | Action                            | Status |
| ----------------- | --------------------------------- | ------ |
| `src/common.py`   | Shared `AnsiStripper` utility     | Done   |
| `src/__init__.py` | Package init                      | Done   |
| `src/clean.py`    | Main cleaning script with classes | Done   |

## Summary

Cleaned barista/minerva log from ~1.6M raw lines down to 51,555 meaningful lines. Removed all tokens, secrets, credentials, bot scanner probes, static assets, auth flow, heartbeats, internal chatter, and 404s. Only API proxy calls (`api xlate`), HTTP access log entries (`/api/`, `/search/`), and POST body data remain.

## Lessons Learned

- Always strip ANSI codes before regex matching on log files
- Brace-depth tracking is more robust than matching specific end patterns
- Start broad (any token value) rather than specific — saves rework
- Scan remaining patterns after each cleanup pass to find more noise
- Blanket 404 removal is better than whack-a-mole with individual bot paths
