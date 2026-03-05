#!/usr/bin/env python3
"""Generate an analysis report from cleaned barista/minerva log files.

Parses two log formats that coexist in the same file:

- **barista api xlate** — timestamped backend API proxy calls
- **Express HTTP access log** — method, path, status, response time, size

Produces a text report covering traffic volume, endpoint usage, response
time percentiles, slowest requests, error breakdown, and hourly traffic
patterns.

Prerequisite: run ``clean.py`` first to strip noise and secrets.

Usage::

    python src/report.py <logfile>

Example::

    python src/report.py hold.log/hold.log
    # Report printed to stdout and saved to hold.log/hold_report.txt
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from urllib.parse import unquote

from src.common import AnsiStripper


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ApiCall:
    """A single barista API proxy call (``api xlate`` line).

    Attributes:
        timestamp: ISO-8601 timestamp string (e.g., ``2026-02-17T15:19:47.216Z``).
        method: HTTP method (``GET`` or ``POST``).
        path: Full path including query string.
        base_path: Path without query string.
    """

    timestamp: str
    method: str
    path: str
    base_path: str

    @property
    def date(self) -> str:
        """Date portion ``YYYY-MM-DD``."""
        return self.timestamp[:10]

    @property
    def hour(self) -> str:
        """Hour portion ``YYYY-MM-DDTHH``."""
        return self.timestamp[:13]


@dataclass
class HttpRequest:
    """A single Express HTTP access log entry.

    Attributes:
        method: HTTP method.
        path: Full URL path (URL-decoded).
        base_path: Path without query string.
        status: HTTP status code.
        time_ms: Response time in milliseconds.
        size: Response body size in bytes (0 if ``-``).
    """

    method: str
    path: str
    base_path: str
    status: int
    time_ms: float
    size: int

    @property
    def is_error(self) -> bool:
        """``True`` if the status code is 4xx or 5xx."""
        return self.status >= 400


@dataclass
class ParsedLog:
    """Container for all parsed records from a log file."""

    api_calls: list[ApiCall] = field(default_factory=list)
    http_requests: list[HttpRequest] = field(default_factory=list)
    body_data_count: int = 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class LogParser:
    """Parse a cleaned barista log file into structured records.

    Recognises three line formats:

    1. ``barista [<ts>]:  api xlate (<METHOD>): [<host>]<path>``
    2. ``<METHOD> <path> <status> <time> ms - <size>``
    3. ``barista [<ts>]:  Received body data: <payload>``
    """

    _API_RE = re.compile(
        r"^barista \[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\]:\s+"
        r"api xlate \((\w+)\):\s+\[http://[^\]]+\](/.+)$"
    )
    _HTTP_RE = re.compile(
        r"^(GET|POST|PUT|DELETE|PATCH|HEAD)\s+(\S+)\s+(\d{3})\s+"
        r"([\d.]+)\s+ms\s+-\s+(-|\d+)$"
    )
    _BODY_RE = re.compile(
        r"^barista \[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\]:\s+"
        r"Received body data:\s+(.+)$"
    )

    @staticmethod
    def _base_path(path: str) -> str:
        return path.split("?")[0]

    def parse(self, filepath: str) -> ParsedLog:
        """Read *filepath* and return a :class:`ParsedLog`."""
        result = ParsedLog()

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                clean = AnsiStripper.strip(line.strip())

                m = self._API_RE.match(clean)
                if m:
                    ts, method, path = m.group(1), m.group(2), m.group(3)
                    result.api_calls.append(
                        ApiCall(ts, method, path, self._base_path(path))
                    )
                    continue

                m = self._HTTP_RE.match(clean)
                if m:
                    method, path, status, time_ms, size = m.groups()
                    path = unquote(path)
                    result.http_requests.append(HttpRequest(
                        method, path, self._base_path(path),
                        int(status), float(time_ms),
                        int(size) if size != "-" else 0,
                    ))
                    continue

                if self._BODY_RE.match(clean):
                    result.body_data_count += 1

        return result


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

class ReportBuilder:
    """Build a human-readable text report from :class:`ParsedLog` data.

    Report sections:

    - **Overview** — total counts and date range.
    - **API Proxy Calls** — method breakdown, top endpoints, daily volume,
      busiest hours.
    - **HTTP Access Log** — method/status breakdown, top endpoints,
      response-time percentiles, slowest requests, error summary,
      per-endpoint average latency.
    """

    def __init__(self):
        self._lines: list[str] = []

    # -- Formatting helpers --------------------------------------------------

    def _header(self, title: str, char: str = "=") -> None:
        self._lines.append(char * 70)
        self._lines.append(title)
        self._lines.append(char * 70)

    def _section(self, title: str) -> None:
        self._lines.append("\n" + "-" * 70)
        self._lines.append(title)
        self._lines.append("-" * 70)

    def _counter_table(self, title: str, counts: Counter, limit: int = 20) -> None:
        total_unique = len(counts)
        self._lines.append(f"\n{title} ({total_unique} unique):")
        for key, count in counts.most_common(limit):
            self._lines.append(f"  {count:>8,}  {key}")

    # -- Report assembly -----------------------------------------------------

    def build(self, data: ParsedLog, filepath: str) -> str:
        """Return the full report as a string."""
        self._header("BARISTA LOG ANALYSIS REPORT")
        self._overview(data, filepath)
        self._api_section(data.api_calls)
        self._http_section(data.http_requests)
        self._lines.append("\n" + "=" * 70)
        self._lines.append("END OF REPORT")
        self._lines.append("=" * 70)
        return "\n".join(self._lines)

    def _overview(self, data: ParsedLog, filepath: str) -> None:
        self._lines.append(f"\nSource: {filepath}")
        self._lines.append(f"API proxy calls (api xlate): {len(data.api_calls):,}")
        self._lines.append(f"HTTP access log entries:     {len(data.http_requests):,}")
        self._lines.append(f"POST body data entries:      {data.body_data_count:,}")
        if data.api_calls:
            dates = [c.date for c in data.api_calls]
            self._lines.append(f"Date range: {min(dates)} to {max(dates)}")

    def _api_section(self, calls: list[ApiCall]) -> None:
        self._section("API PROXY CALLS (api xlate)")
        if not calls:
            self._lines.append("\nNo API calls found.")
            return

        self._lines.append("\nBy HTTP method:")
        for method, count in Counter(c.method for c in calls).most_common():
            self._lines.append(f"  {method:8s} {count:>8,}")

        self._counter_table("Top endpoints", Counter(c.base_path for c in calls))

        date_counts = Counter(c.date for c in calls)
        self._lines.append(f"\nRequests by date ({len(date_counts)} days):")
        for date in sorted(date_counts):
            self._lines.append(f"  {date}  {date_counts[date]:>8,}")

        hour_counts = Counter(c.hour for c in calls)
        self._lines.append("\nTop 15 busiest hours:")
        for hour, count in hour_counts.most_common(15):
            bar = "#" * min(count // 10, 50)
            self._lines.append(f"  {hour}  {count:>6,}  {bar}")

    def _http_section(self, requests: list[HttpRequest]) -> None:
        self._section("HTTP ACCESS LOG")
        if not requests:
            self._lines.append("\nNo HTTP requests found.")
            return

        # Method breakdown
        self._lines.append("\nBy HTTP method:")
        for method, count in Counter(r.method for r in requests).most_common():
            self._lines.append(f"  {method:8s} {count:>8,}")

        # Status codes
        status_counts = Counter(r.status for r in requests)
        self._lines.append("\nBy status code:")
        for status, count in sorted(status_counts.items()):
            self._lines.append(f"  {status}  {count:>8,}")

        # Top endpoints
        self._counter_table("Top endpoints", Counter(r.base_path for r in requests))

        # Response time percentiles
        times = sorted(r.time_ms for r in requests)
        n = len(times)
        self._lines.append("\nResponse time (ms):")
        self._lines.append(f"  Min:    {times[0]:>12,.1f}")
        self._lines.append(f"  Median: {times[n // 2]:>12,.1f}")
        self._lines.append(f"  P95:    {times[int(n * 0.95)]:>12,.1f}")
        self._lines.append(f"  P99:    {times[int(n * 0.99)]:>12,.1f}")
        self._lines.append(f"  Max:    {times[-1]:>12,.1f}")

        # Slowest requests
        slowest = sorted(requests, key=lambda r: r.time_ms, reverse=True)[:15]
        self._lines.append("\nTop 15 slowest requests:")
        for r in slowest:
            self._lines.append(
                f"  {r.time_ms:>12,.1f} ms  {r.status}  {r.method} {r.path[:80]}"
            )

        # Errors
        errors = [r for r in requests if r.is_error]
        if errors:
            self._lines.append(f"\nErrors ({len(errors):,} total):")
            error_ep = Counter((r.status, r.base_path) for r in errors)
            for (status, ep), count in error_ep.most_common(15):
                self._lines.append(f"  {count:>6,}  {status}  {ep}")

        # Average response time by endpoint
        ep_times: dict[str, list[float]] = defaultdict(list)
        for r in requests:
            ep_times[r.base_path].append(r.time_ms)
        ep_avg = [(ep, sum(t) / len(t), len(t)) for ep, t in ep_times.items()]
        ep_avg.sort(key=lambda x: x[1], reverse=True)
        self._lines.append("\nAvg response time by endpoint (top 15 slowest):")
        for ep, avg, count in ep_avg[:15]:
            self._lines.append(f"  {avg:>10,.1f} ms  ({count:>5,} reqs)  {ep}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def generate_report(filepath: str, output: str | None = None) -> str:
    """Parse *filepath* and return the report text.

    If *output* is given, the report is also written to that path.
    Otherwise it is written next to *filepath* as ``<name>_report.txt``.
    """
    parser = LogParser()
    data = parser.parse(filepath)

    report = ReportBuilder().build(data, filepath)

    report_path = output or filepath.rsplit(".", 1)[0] + "_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    return report_path


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description="Generate an analysis report from a cleaned barista/minerva log file.",
    )
    ap.add_argument("file", help="Path to the cleaned log file.")
    ap.add_argument(
        "-o", "--output",
        help="Output path for the report (default: <file>_report.txt).",
    )
    args = ap.parse_args()

    report_path = generate_report(args.file, args.output)
    print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    main()
