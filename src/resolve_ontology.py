"""Pre-pipeline step: build / update the local ontology label cache.

Scans one or more log files (or the existing cache) for OBO ontology IDs
(GO, RO, BFO, ECO, …) and resolves their human-readable labels via the
EBI OLS4 API.  Results are saved to ``ontology_cache.json`` at the project
root so that downstream scripts (``humanize.py``) can use them offline.

Usage::

    python src/resolve_ontology.py [FILES...]

If no files are given, only missing IDs already in the cache are refreshed.
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

# Prefixes we treat as OBO ontology terms
ONTOLOGY_PREFIXES = {"GO", "RO", "BFO", "ECO", "SO", "CHEBI", "CL", "UBERON"}
_ONTOLOGY_ID_RE = re.compile(r"\b([A-Z]{2,}:\d{5,})\b")

CACHE_PATH = Path(__file__).resolve().parent.parent / "ontology_cache.json"
OLS_SEARCH = "https://www.ebi.ac.uk/ols4/api/search"


def load_cache() -> dict[str, str]:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_cache(labels: dict[str, str]) -> None:
    CACHE_PATH.write_text(
        json.dumps(labels, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def collect_ids_from_text(text: str) -> set[str]:
    return {
        m for m in _ONTOLOGY_ID_RE.findall(text)
        if m.split(":")[0] in ONTOLOGY_PREFIXES
    }


def collect_ids_from_files(paths: list[str]) -> set[str]:
    ids: set[str] = set()
    for p in paths:
        ids |= collect_ids_from_text(Path(p).read_text(encoding="utf-8"))
    return ids


def fetch_label(obo_id: str) -> str | None:
    """Query OLS for the label of *obo_id*. Returns None on failure."""
    prefix = obo_id.split(":")[0].lower()
    urls = [
        f"{OLS_SEARCH}?q={obo_id}&exact=true&queryFields=obo_id&ontology={prefix}",
        f"{OLS_SEARCH}?q={obo_id}&exact=true&queryFields=obo_id",
    ]
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
            docs = data.get("response", {}).get("docs", [])
            if docs:
                return docs[0].get("label")
        except Exception:
            pass
    return None


def resolve(ids: set[str], labels: dict[str, str]) -> int:
    """Resolve missing IDs into *labels* dict. Returns count of newly resolved."""
    missing = sorted(
        oid for oid in ids
        if oid not in labels and oid.split(":")[0] in ONTOLOGY_PREFIXES
    )
    if not missing:
        print("All IDs already cached.")
        return 0

    resolved = 0
    for i, obo_id in enumerate(missing, 1):
        print(f"  [{i}/{len(missing)}] {obo_id} ... ", end="", flush=True)
        label = fetch_label(obo_id)
        if label:
            labels[obo_id] = label
            resolved += 1
            print(label)
        else:
            print("NOT FOUND")

    return resolved


def main() -> None:
    labels = load_cache()
    files = sys.argv[1:]

    if files:
        ids = collect_ids_from_files(files)
        print(f"Found {len(ids)} ontology IDs in {len(files)} file(s).")
    else:
        ids = set(labels.keys())
        print(f"No files given; refreshing {len(ids)} cached IDs.")

    resolved = resolve(ids, labels)
    save_cache(labels)
    print(f"Done. {resolved} new labels resolved. Cache: {CACHE_PATH}")


if __name__ == "__main__":
    main()
