"""Extract historical TTL file versions from a noctua-models git repo.

For each commit that touched a model file, extracts the file content via
``git show`` and saves it with a timestamp-based filename — but only if
the content differs from the previously saved version.

Usage::

    python src/extract_versions.py <repo_path> <model_id> <output_dir> [--after DATE]

Example::

    python src/extract_versions.py C:/work/go/noctua-models-temp 693b3c0900004140 downloads/models --after 2026-02-01
"""

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CommitInfo:
    """A commit that touched the target file."""

    hash: str
    iso_date: str
    message: str


@dataclass
class ExtractionStats:
    """Counts for a version-extraction run."""

    commits_found: int = 0
    versions_saved: int = 0
    duplicates_skipped: int = 0

    def __str__(self) -> str:
        return (
            f"{self.commits_found} commits found, "
            f"{self.versions_saved} unique versions saved, "
            f"{self.duplicates_skipped} unchanged skipped."
        )


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

class GitFileHistory:
    """Query git history for a single file in a repository."""

    def __init__(self, repo_path: str):
        self._repo = repo_path

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", self._repo, *args],
            capture_output=True, text=True, encoding="utf-8",
        )
        result.check_returncode()
        return result.stdout

    def list_commits(self, file_path: str, after: str | None = None) -> list[CommitInfo]:
        """Return commits that touched *file_path*, oldest first."""
        cmd = ["log", "--format=%h %aI %s", "--follow"]
        if after:
            cmd.append(f"--after={after}")
        cmd += ["--", file_path]

        lines = self._run(*cmd).strip().splitlines()
        commits = []
        for line in lines:
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                commits.append(CommitInfo(parts[0], parts[1], parts[2]))
        commits.reverse()  # oldest first
        return commits

    def show_file(self, commit_hash: str, file_path: str) -> str:
        """Return the content of *file_path* at *commit_hash*."""
        return self._run("show", f"{commit_hash}:{file_path}")


# ---------------------------------------------------------------------------
# Version extractor
# ---------------------------------------------------------------------------

class VersionExtractor:
    """Extract unique file versions from git history to disk."""

    def __init__(self, repo_path: str, model_id: str, output_dir: str):
        self._git = GitFileHistory(repo_path)
        self._model_id = model_id
        self._file_path = f"models/{model_id}.ttl"
        self._outdir = Path(output_dir)

    @staticmethod
    def _content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _folder_name(iso_date: str) -> str:
        """Convert ``2026-02-20T08:40:02-08:00`` → ``2026-02-20_08-40-02``.

        Uses dashes instead of colons (Windows-safe) while staying readable.
        """
        # Split off timezone
        if "+" in iso_date:
            dt_part = iso_date.split("+")[0]
        else:
            # e.g. 2026-02-20T08:40:02-08:00 — timezone starts at 3rd dash
            dt_part = iso_date[:19]
        # 2026-02-20T08:40:02 → 2026-02-20_08-40-02
        return dt_part.replace("T", "_").replace(":", "-")

    def extract(self, after: str | None = None) -> ExtractionStats:
        """Extract all unique versions.

        Two layouts in sibling directories:

        - ``<outdir>/by_folder/<timestamp>/<model_id>.ttl`` — Minerva-safe
        - ``<outdir>/by_file/<timestamp>_<model_id>.ttl`` — easy browsing
        """
        folder_dir = self._outdir / "by_folder"
        file_dir = self._outdir / "by_file"
        folder_dir.mkdir(parents=True, exist_ok=True)
        file_dir.mkdir(parents=True, exist_ok=True)

        stats = ExtractionStats()
        commits = self._git.list_commits(self._file_path, after=after)
        stats.commits_found = len(commits)

        prev_hash = None
        for commit in commits:
            content = self._git.show_file(commit.hash, self._file_path)
            chash = self._content_hash(content)

            if chash == prev_hash:
                stats.duplicates_skipped += 1
                continue

            prev_hash = chash
            ts_name = self._folder_name(commit.iso_date)

            # Subfolder layout: by_folder/<timestamp>/<model_id>.ttl
            ts_dir = folder_dir / ts_name
            ts_dir.mkdir(parents=True, exist_ok=True)
            with open(ts_dir / f"{self._model_id}.ttl", "w", encoding="utf-8") as f:
                f.write(content)

            # Flat layout: by_file/<timestamp>_<model_id>.ttl
            with open(file_dir / f"{ts_name}_{self._model_id}.ttl", "w", encoding="utf-8") as f:
                f.write(content)

            stats.versions_saved += 1

        return stats


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def extract_versions(
    repo_path: str,
    model_id: str,
    output_dir: str,
    after: str | None = None,
) -> ExtractionStats:
    """Extract unique TTL versions for *model_id* into *output_dir*."""
    extractor = VersionExtractor(repo_path, model_id, output_dir)
    return extractor.extract(after=after)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract historical TTL versions from noctua-models git repo.",
    )
    parser.add_argument("repo", help="Path to the noctua-models git repo.")
    parser.add_argument("model_id", help="Model ID (e.g. 693b3c0900004140).")
    parser.add_argument("outdir", help="Output directory for extracted TTL files.")
    parser.add_argument(
        "--after",
        help="Only include commits after this date (e.g. 2026-02-01).",
    )
    args = parser.parse_args()

    stats = extract_versions(args.repo, args.model_id, args.outdir, after=args.after)
    print(f"Done. {stats}")
    print(f"Output: {args.outdir}")


if __name__ == "__main__":
    main()
