#!/usr/bin/env python3
"""Clean sensitive and noisy data from barista/minerva log files.

Strips secrets, token blocks, authentication noise, bot scanner probes,
static asset requests, and internal chatter — leaving only meaningful
API proxy calls and HTTP access log entries for analysis.

Prerequisite for ``report.py``.

Usage::

    python src/clean.py <logfile>

Example::

    python src/clean.py hold.log/hold.log
    # Done. Removed 120,000 lines. 51,555 lines remain (from 171,555 total).
"""

import re
from dataclasses import dataclass

from src.common import AnsiStripper


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

class BlockFilter:
    """Skip multi-line brace-delimited blocks that start with a trigger pattern.

    Uses brace-depth tracking so nested ``{}`` inside arrays/objects are
    handled correctly regardless of block length or structure.

    Args:
        patterns: Regex strings; any line matching one of these starts a block.

    Example block that gets removed::

        { token: 'abc123',
          uri: 'TEMP:editor',
          groups:
           [ { label: 'GO Central', id: 'http://geneontology.org' } ],
          'email-md5': null }
    """

    def __init__(self, patterns: list[str]):
        self._start_re = re.compile("|".join(patterns))
        self._active = False
        self._depth = 0

    def should_skip(self, line: str) -> bool:
        """Return ``True`` if *line* is part of a block that should be removed."""
        if not self._active:
            if self._start_re.search(line):
                self._active = True
                self._depth = line.count("{") - line.count("}")
                return True
            return False

        self._depth += line.count("{") - line.count("}")
        if self._depth <= 0:
            self._active = False
        return True


class LineFilter:
    """Remove individual lines that match any of the given patterns.

    Args:
        patterns: Regex strings combined with ``|``.  Uses ``search()``
            (not ``match()``) so patterns work regardless of line prefix.
    """

    def __init__(self, patterns: list[str]):
        self._re = re.compile("|".join(patterns))

    def should_skip(self, line: str) -> bool:
        """Return ``True`` if *line* matches any noise pattern."""
        return bool(self._re.search(line))


class TokenRedactor:
    """Redact token values from URL query strings.

    Replaces ``token=<value>&`` and ``barista_token=<value>&`` with an
    empty string.  The rest of the URL is preserved so the request path
    and other parameters remain available for analysis.
    """

    _RE = re.compile(r"(barista_)?token=[a-zA-Z0-9]+&?")

    @classmethod
    def redact(cls, text: str) -> str:
        """Return *text* with token query-param values removed."""
        return cls._RE.sub("", text)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

@dataclass
class CleanStats:
    """Counts of lines processed during a cleaning run."""

    total_lines: int = 0
    removed: int = 0
    kept: int = 0

    def __str__(self) -> str:
        return (
            f"Removed {self.removed:,} lines. "
            f"{self.kept:,} lines remain (from {self.total_lines:,} total)."
        )


# ---------------------------------------------------------------------------
# Filter configuration
# ---------------------------------------------------------------------------

#: Patterns that start a multi-line block to remove.
BLOCK_PATTERNS = [
    # Token entity objects — bare, ``sess``-prefixed, or ``barista [ts]:``-prefixed
    r"^(.+\s+)?(sess )?\{ token: '.*',?$",
    # GitHub OAuth credentials
    r"^secrets for github \{ clientID:",
]

#: Single-line noise patterns to remove entirely.
NOISE_PATTERNS = [
    # -- Barista internal chatter --
    r"^barista \[.*\]:\s+srv disconnect$",
    r"^barista \[.*\]:\s+process heartbeat request$",
    r"^barista \[.*\]:\s+Skip broadcast",
    r"^barista \[.*\]:\s+Broadcast (rebuild|merge)\.",
    r"^barista \[.*\]:\s+looks like a token was attempted",
    r"^barista \[.*\]:\s+no token was attempted",
    r"^barista \[.*\]:\s+looks like (POST|GET)$",
    r"^barista \[.*\]:\s+call using session:",
    r"^barista \[.*\]:\s+got user info for:",
    r"^barista \[.*\]:\s+respond to query from",
    r"^barista \[.*\]:\s+(Barista |Will |REPL|debug level)",
    r"^barista \[.*\]:\s+Anonymous editor token:",
    r"^barista \[.*\]:\s+(admin|editor) token \(self\):",
    # -- Static assets --
    r"^(GET|POST|HEAD|PUT|DELETE|PATCH) .*\.(js|css|ico|png|jpg|gif|svg|woff|ttf|eot|map)",
    # -- Health checks & auth metadata --
    r"^HEAD /status ",
    r"/user_info_by_token/",
    r"^(GET|POST) /users\s",
    r"^(GET|POST) /groups\s",
    # -- Auth flow --
    r"/login",
    r"/auth/",
    r"^Start GitHub auth",
    r"^Recovered return URL from session",
    r"^/auth/github/callback GET got",
    # -- All 404 responses (scanner bots, missing pages) --
    r"^(GET|POST|HEAD|PUT|DELETE|PATCH) .+ 404 ",
    # -- Non-API junk paths --
    r"^(GET|POST|HEAD|PUT|DELETE|PATCH) /status",
    r"^(GET|POST|HEAD|PUT|DELETE|PATCH) /user_info\b",
    r"^(GET|POST|HEAD|PUT|DELETE|PATCH) /logout",
    r"^(GET|POST|HEAD|PUT|DELETE|PATCH) /users/",
    r"^(GET|POST|HEAD|PUT|DELETE|PATCH) /robots\.txt",
    r"^(GET|POST|HEAD|PUT|DELETE|PATCH) /(#|$| )",
    r"^(GET|POST|HEAD|PUT|DELETE|PATCH) //",
    r"^(GET|POST|HEAD|PUT|DELETE|PATCH) /groups/",
    # -- Startup & misc --
    r"^Express server listening",
    r"^undefined$",
    r"^Developer \(",
    # -- Raw response body fragments leaked into log --
    r'^\[?\{"groups":\[',
    r"^\d{4,6}$",
]


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def clean_file(filepath: str, output: str | None = None) -> CleanStats:
    """Clean *filepath*, writing results to *output* (or in-place if ``None``).

    Processing pipeline per line:

    1. Strip ANSI escape codes for pattern matching.
    2. ``BlockFilter`` — skip if inside a multi-line token/secrets block.
    3. ``LineFilter`` — skip if the line matches any single-line noise pattern.
    4. ``TokenRedactor`` — redact token values from URLs (line is kept).
    """
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    block_filter = BlockFilter(BLOCK_PATTERNS)
    line_filter = LineFilter(NOISE_PATTERNS)
    stats = CleanStats(total_lines=len(lines))

    result = []
    for line in lines:
        clean_line = AnsiStripper.strip(line.rstrip("\n"))

        if block_filter.should_skip(clean_line):
            stats.removed += 1
            continue

        if line_filter.should_skip(clean_line):
            stats.removed += 1
            continue

        result.append(TokenRedactor.redact(line))

    stats.kept = len(result)

    dest = output or filepath
    with open(dest, "w", encoding="utf-8") as f:
        f.writelines(result)

    return stats


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Clean sensitive and noisy data from barista/minerva log files.",
    )
    parser.add_argument("file", help="Path to the raw log file.")
    parser.add_argument(
        "-o", "--output",
        help="Output path for cleaned log (default: overwrite input file in-place).",
    )
    args = parser.parse_args()

    stats = clean_file(args.file, args.output)
    dest = args.output or args.file
    print(f"Done. {stats}")
    print(f"Output: {dest}")


if __name__ == "__main__":
    main()
