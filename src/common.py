"""Shared utilities for barista log processing src."""

import re


class AnsiStripper:
    """Removes ANSI escape codes from text.

    ANSI codes are embedded in Express/Morgan HTTP log lines as color formatting
    (e.g., ``\\x1b[32m200\\x1b[0m`` for green status codes). These must be stripped
    before any regex matching or text analysis.

    Example::

        >>> AnsiStripper.strip("\\x1b[0mGET /search \\x1b[32m200\\x1b[0m")
        'GET /search 200'
    """

    _RE = re.compile(r"\x1b\[[0-9;]*m")

    @classmethod
    def strip(cls, text: str) -> str:
        """Strip all ANSI escape sequences from *text*."""
        return cls._RE.sub("", text)
