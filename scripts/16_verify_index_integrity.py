"""Verify index integrity across Postgres, Qdrant, and embedding manifest.

Outputs report to data/processed/index_integrity_report.json with:
- database counts
- qdrant collection counts
- manifest counts
- consistency checks and pass/fail status
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from loguru import logger
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from src.config.settings import settings
from src.database.models import Case
from src.features.similar_cases.vector_store import VectorStore


def load_manifest_stats(manifest_path: Path) -> dict[str, int]:
    """Load embedding manifest stats.

    Args:
        manifest_path: Path to manifest file.

    Returns:
        Dictionary with manifest counters.
    """
    if not manifest_path.exists():
        return {
            "total_entries": 0,
            "indexed_entries": 0,
            "failed_entries": 0,
            "unique_case_ids": 0,
        }

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return {
            "total_entries": 0,
            "indexed_entries": 0,
            "failed_entries": 0,
            "unique_case_ids": 0,
        }

    indexed_entries = 0
    failed_entries = 0
    unique_case_ids = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        case_id = item.get("case_id")
        if case_id is not None:
            unique_case_ids.add(int(case_id))
        status = str(item.get("status", "")).lower()
        if status == "indexed":
            indexed_entries += 1
        elif status == "failed":
            failed_entries += 1

    return {
        "total_entries": len(data),
        "indexed_entries": indexed_entries,
        "failed_entries": failed_entries,
        "unique_case_ids": len(unique_case_ids),
    }


def compute_integrity_checks(
    db_non_invalid: int,
    qdrant_counts: dict[str, int],
    manifest_stats: dict[str, int],
    tolerance: int = 0,
) -> dict[str, Any]:
    """Compute consistency checks and overall pass/fail.

    Args:
        db_non_invalid: Non-invalid case count from database.
        qdrant_counts: Collection point counts.
        manifest_stats: Manifest counters.
        tolerance: Allowed absolute delta.

    Returns:
        Integrity checks and status.
    """
    checks = {}
    overall_pass = True

    combined_count = qdrant_counts.get("combined", 0)
    factual_count = qdrant_counts.get("factual", 0)
    legal_count = qdrant_counts.get("legal", 0)
    fulltext_count = qdrant_counts.get("fulltext", 0)

    for label, value in {
        "combined_matches_db_non_invalid": combined_count,
        "factual_matches_db_non_invalid": factual_count,
        "legal_matches_db_non_invalid": legal_count,
    }.items():
        delta = value - db_non_invalid
        passed = abs(delta) <= tolerance
        checks[label] = {
            "expected": db_non_invalid,
            "actual": value,
            "delta": delta,
            "pass": passed,
        }
        overall_pass = overall_pass and passed

    fulltext_delta = fulltext_count - db_non_invalid
    checks["fulltext_matches_db_non_invalid"] = {
        "expected": db_non_invalid,
        "actual": fulltext_count,
        "delta": fulltext_delta,
        "pass": abs(fulltext_delta) <= tolerance,
    }

    manifest_indexed = manifest_stats.get("indexed_entries", 0)
    manifest_delta = manifest_indexed - combined_count
    checks["manifest_indexed_matches_combined"] = {
        "expected": combined_count,
        "actual": manifest_indexed,
        "delta": manifest_delta,
        "pass": abs(manifest_delta) <= max(1, tolerance),
    }

    overall_pass = overall_pass and checks["manifest_indexed_matches_combined"]["pass"]

    return {
        "status": "pass" if overall_pass else "warn",
        "checks": checks,
    }


def main() -> None:
    """Run index integrity verification and write report."""
    engine = create_engine(settings.database_url, echo=False)
    session_local = sessionmaker(bind=engine)
    session = session_local()

    try:
        db_total = session.query(func.count(Case.id)).scalar() or 0
        db_non_invalid = (
            session.query(func.count(Case.id))
            .filter(Case.validation_status != "invalid")
            .scalar()
            or 0
        )
    finally:
        session.close()

    qdrant_counts = {"combined": 0, "factual": 0, "legal": 0, "fulltext": 0}
    qdrant_error = None
    try:
        vector_store = VectorStore(host=settings.qdrant_host, port=settings.qdrant_port)
        stats = vector_store.get_collection_stats()
        qdrant_counts = {
            "combined": int(
                stats.get(vector_store.COLLECTION_COMBINED, {}).get("points_count") or 0
            ),
            "factual": int(
                stats.get(vector_store.COLLECTION_FACTUAL, {}).get("points_count") or 0
            ),
            "legal": int(
                stats.get(vector_store.COLLECTION_LEGAL, {}).get("points_count") or 0
            ),
            "fulltext": int(
                stats.get(vector_store.COLLECTION_FULLTEXT, {}).get("points_count") or 0
            ),
        }
    except Exception as exc:
        qdrant_error = str(exc)
        logger.warning(
            "Failed to read Qdrant stats via client; retrying with HTTP",
            error=qdrant_error,
        )
        qdrant_counts, http_error = _fetch_qdrant_counts_via_http()
        if http_error:
            qdrant_error = f"client_error={qdrant_error}; http_error={http_error}"
        else:
            qdrant_error = None

    manifest_path = Path("data/processed/embedding_manifest.json")
    manifest_stats = load_manifest_stats(manifest_path)

    integrity = compute_integrity_checks(
        db_non_invalid=int(db_non_invalid),
        qdrant_counts=qdrant_counts,
        manifest_stats=manifest_stats,
    )

    report = {
        "database": {
            "total_cases": int(db_total),
            "non_invalid_cases": int(db_non_invalid),
        },
        "qdrant": {
            "counts": qdrant_counts,
            "error": qdrant_error,
        },
        "manifest": manifest_stats,
        "integrity": integrity,
    }

    output_path = Path("data/processed/index_integrity_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info(
        "Index integrity report written",
        path=str(output_path),
        status=integrity["status"],
    )


def _fetch_qdrant_counts_via_http() -> tuple[dict[str, int], str | None]:
    """Fetch collection counts via Qdrant HTTP API as compatibility fallback."""
    api_host = (
        settings.qdrant_host
        if settings.qdrant_host not in {"0.0.0.0", "qdrant"}
        else "127.0.0.1"
    )
    base = f"http://{api_host}:{settings.qdrant_port}"
    collections = {
        "combined": "nyaya_cases_combined",
        "factual": "nyaya_cases_factual",
        "legal": "nyaya_cases_legal",
        "fulltext": "nyaya_cases_fulltext",
    }
    counts = {key: 0 for key in collections}
    try:
        with httpx.Client(timeout=20) as client:
            for key, name in collections.items():
                response = client.get(f"{base}/collections/{name}")
                response.raise_for_status()
                payload = response.json()
                counts[key] = int(payload.get("result", {}).get("points_count") or 0)
    except Exception as exc:
        return counts, str(exc)
    return counts, None


if __name__ == "__main__":
    main()
