"""Cache metadata writer for feature-spec-builder extract scripts.

Called by `extract_figma_page.py` and `extract_axure_page.py` after a
successful extraction. Writes a sibling `<output>.cache.json` file that
the feature-spec-builder skill flow can read to decide whether a previous
extraction can be reused (see `references/cache-policy.md`).

Schema is intentionally simple and human-readable; bump `SCHEMA_VERSION`
when fields change in incompatible ways.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 1
DEFAULT_TTL_DAYS = 7


def write_cache_metadata(
    output_path: str | Path,
    *,
    source_type: str,
    source_url: str,
    extractor_version: str,
    source_page: Optional[str] = None,
    skill_version: str = "unspecified",
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> Path:
    """Write a `.cache.json` sibling describing the just-saved extraction output.

    Args:
        output_path: path to the freshly-written output JSON (e.g. figma_page.json).
        source_type: "figma" or "axure".
        source_url: original URL passed to the extractor.
        extractor_version: extractor script's internal version tag. This is the
            cache-bust factor honoured by extract_with_cache.check_cache_hit() —
            bump it whenever an extractor's output format/logic changes.
        source_page: optional Figma page name (only relevant for Figma).
        skill_version: feature-spec-builder skill version. Informational only —
            the extraction output is independent of skill orchestration version,
            so this field is NOT used for cache invalidation. Defaults to
            "unspecified" rather than a stale literal to avoid lying in metadata.
        ttl_days: cache validity window in days; consumers may decide to ignore.

    Returns:
        Path to the written `.cache.json` file.
    """
    output_path = Path(output_path)
    cache_path = output_path.with_suffix(".cache.json")

    output_sha = hashlib.sha256(output_path.read_bytes()).hexdigest()

    fingerprint_key = "|".join(
        [source_type, source_url, source_page or "", extractor_version]
    )
    fingerprint = hashlib.sha256(fingerprint_key.encode("utf-8")).hexdigest()

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "skill_version": skill_version,
        "extractor_version": extractor_version,
        "source_type": source_type,
        "source_url": source_url,
        "source_page": source_page,
        "fingerprint": fingerprint,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "ttl_days": ttl_days,
        "output_path": str(output_path),
        "output_sha256": output_sha,
    }

    cache_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return cache_path
