"""Rebuild embedding manifest from current combined Qdrant collection IDs."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger
from qdrant_client import QdrantClient

from src.config.settings import settings


def main() -> None:
    """Rebuild data/processed/embedding_manifest.json from live Qdrant IDs."""
    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    ids: list[int] = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name="nyaya_cases_combined",
            limit=1000,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        ids.extend(int(point.id) for point in points if point.id is not None)
        if offset is None:
            break

    ids = sorted(set(ids))
    manifest = [{"case_id": case_id, "status": "indexed"} for case_id in ids]

    output = Path("data/processed/embedding_manifest.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    logger.info("Manifest rebuilt from Qdrant", count=len(manifest), path=str(output))


if __name__ == "__main__":
    main()
