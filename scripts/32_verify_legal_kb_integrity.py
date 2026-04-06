"""Verify legal KB integrity across chunks, manifest, and Qdrant index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from loguru import logger
from qdrant_client import QdrantClient

from src.config.settings import settings


COLLECTION_NAME = "nyaya_legal_kb"
REQUIRED_FIELDS = [
    "chunk_id",
    "source_id",
    "source_type",
    "act_name",
    "section_or_article",
    "text",
    "source_version_hash",
]


def parse_args() -> argparse.Namespace:
    """Parse command-line args for legal KB integrity check."""
    parser = argparse.ArgumentParser(description="Verify legal KB integrity")
    parser.add_argument(
        "--chunks",
        type=str,
        default="data/processed/legal_kb_chunks.jsonl",
        help="Prepared chunks JSONL path",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default="data/processed/legal_kb_embedding_manifest.json",
        help="Embedding manifest path",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/processed/legal_kb_integrity_report.json",
        help="Integrity report output path",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL records from file path."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def load_manifest(path: Path) -> list[dict[str, Any]]:
    """Load manifest JSON array from file path."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def evaluate_metadata(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate required metadata coverage for prepared chunks."""
    missing_counts = {field: 0 for field in REQUIRED_FIELDS}
    for chunk in chunks:
        for field in REQUIRED_FIELDS:
            value = chunk.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing_counts[field] += 1

    total = len(chunks)
    coverage = {
        field: (1.0 - (count / total)) if total > 0 else 0.0
        for field, count in missing_counts.items()
    }
    return {
        "total_chunks": total,
        "missing_counts": missing_counts,
        "coverage": coverage,
    }


def get_qdrant_points_count() -> tuple[int, str | None]:
    """Fetch point count for legal KB collection."""
    try:
        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        info = client.get_collection(collection_name=COLLECTION_NAME)
        return int(info.points_count or 0), None
    except Exception as exc:
        return 0, str(exc)


def compute_checks(
    chunks_count: int,
    indexed_count: int,
    failed_count: int,
    qdrant_count: int,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Compute pass/warn checks for legal KB artifacts."""
    checks = {
        "qdrant_matches_indexed_manifest": {
            "expected": indexed_count,
            "actual": qdrant_count,
            "delta": qdrant_count - indexed_count,
            "pass": qdrant_count == indexed_count,
        },
        "indexed_plus_failed_equals_chunks": {
            "expected": chunks_count,
            "actual": indexed_count + failed_count,
            "delta": (indexed_count + failed_count) - chunks_count,
            "pass": (indexed_count + failed_count) == chunks_count,
        },
    }

    metadata_pass = all(
        float(metadata["coverage"].get(field, 0.0)) >= 0.99 for field in REQUIRED_FIELDS
    )
    checks["required_metadata_coverage"] = {
        "expected": ">=0.99 per required field",
        "actual": metadata["coverage"],
        "pass": metadata_pass,
    }

    overall_pass = all(bool(row["pass"]) for row in checks.values())
    return {
        "status": "pass" if overall_pass else "warn",
        "checks": checks,
    }


def main() -> None:
    """Run legal KB integrity verification and emit report."""
    args = parse_args()
    chunks_path = Path(args.chunks)
    manifest_path = Path(args.manifest)
    output_path = Path(args.output)

    chunks = load_jsonl(chunks_path)
    manifest = load_manifest(manifest_path)

    indexed_count = sum(1 for row in manifest if row.get("status") == "indexed")
    failed_count = sum(1 for row in manifest if row.get("status") == "failed")

    metadata = evaluate_metadata(chunks)
    qdrant_count, qdrant_error = get_qdrant_points_count()

    integrity = compute_checks(
        chunks_count=len(chunks),
        indexed_count=indexed_count,
        failed_count=failed_count,
        qdrant_count=qdrant_count,
        metadata=metadata,
    )

    report = {
        "collection": COLLECTION_NAME,
        "chunks": {
            "path": str(chunks_path),
            "count": len(chunks),
        },
        "manifest": {
            "path": str(manifest_path),
            "total_rows": len(manifest),
            "indexed": indexed_count,
            "failed": failed_count,
        },
        "qdrant": {
            "points_count": qdrant_count,
            "error": qdrant_error,
        },
        "metadata": metadata,
        "integrity": integrity,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info(
        "Legal KB integrity report written",
        path=str(output_path),
        status=integrity["status"],
    )


if __name__ == "__main__":
    main()
