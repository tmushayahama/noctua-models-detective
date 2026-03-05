"""Fetch and cache GO contributor nicknames and group shorthands.

Downloads users.yaml and groups.yaml from the geneontology/go-site repo,
caches them locally, and provides substitution functions for use in
humanize and diff output.

Usage (standalone)::

    python src/resolve_metadata.py

This refreshes the local cache. Normally called as part of the pipeline.
"""

import json
import re
import urllib.request
from pathlib import Path

import yaml

CACHE_PATH = Path(__file__).resolve().parent.parent / "metadata_cache.json"

_USERS_URL = (
    "https://raw.githubusercontent.com/geneontology/go-site/master/metadata/users.yaml"
)
_GROUPS_URL = (
    "https://raw.githubusercontent.com/geneontology/go-site/master/metadata/groups.yaml"
)


def load_cache() -> dict:
    """Load the metadata cache (users + groups)."""
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"users": {}, "groups": {}}


def save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _fetch_yaml(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "val_analysis/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return yaml.safe_load(resp.read().decode("utf-8"))


def fetch_users() -> dict[str, str]:
    """Return {uri: nickname} from the GO users.yaml."""
    entries = _fetch_yaml(_USERS_URL)
    result = {}
    for entry in entries:
        uri = entry.get("uri", "")
        nickname = entry.get("nickname", "")
        if uri and nickname:
            result[uri] = nickname
    return result


def fetch_groups() -> dict[str, str]:
    """Return {id_url: shorthand} from the GO groups.yaml."""
    entries = _fetch_yaml(_GROUPS_URL)
    result = {}
    for entry in entries:
        gid = entry.get("id", "")
        shorthand = entry.get("shorthand", "")
        if gid and shorthand:
            result[gid] = shorthand
    return result


def refresh_cache() -> dict:
    """Fetch fresh users + groups from GitHub and update the cache."""
    cache = load_cache()
    print("  Fetching users.yaml ...")
    cache["users"] = fetch_users()
    print(f"  {len(cache['users'])} users loaded.")
    print("  Fetching groups.yaml ...")
    cache["groups"] = fetch_groups()
    print(f"  {len(cache['groups'])} groups loaded.")
    save_cache(cache)
    return cache


# ---------------------------------------------------------------------------
# Substitution
# ---------------------------------------------------------------------------

_ORCID_RE = re.compile(r"https://orcid\.org/[\dX-]+")
_PROVIDER_RE = re.compile(r"https?://[^\s,)]+")


def substitute_metadata(text: str, cache: dict | None = None) -> str:
    """Replace contributor URIs with nicknames and group URLs with shorthands."""
    if cache is None:
        cache = load_cache()

    users = cache.get("users", {})
    groups = cache.get("groups", {})

    if not users and not groups:
        return text

    def _repl_contributor(m: re.Match) -> str:
        uri = m.group(0)
        name = users.get(uri)
        return f"{name} ({uri})" if name else uri

    # Replace ORCIDs after "contributor: "
    text = re.sub(r"(contributor: )" + _ORCID_RE.pattern, lambda m: m.group(1) + _repl_contributor(re.search(_ORCID_RE, m.group(0))), text)

    # Replace group URLs after "providedBy: "
    def _repl_group(m: re.Match) -> str:
        prefix = m.group(1)
        url = m.group(2)
        shorthand = groups.get(url)
        return f"{prefix}{shorthand} ({url})" if shorthand else m.group(0)

    text = re.sub(r"(providedBy: )(https?://[^\s,)]+)", _repl_group, text)

    # Also handle "by <provider>" in humanize summary lines
    def _repl_by_provider(m: re.Match) -> str:
        url = m.group(1)
        shorthand = groups.get(url)
        return f"by {shorthand} ({url})" if shorthand else m.group(0)

    text = re.sub(r"by (https?://[^\s\]\),]+)", _repl_by_provider, text)

    return text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    cache = refresh_cache()
    print(f"Cache saved to {CACHE_PATH}")


if __name__ == "__main__":
    main()
