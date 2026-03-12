"""Sync Qdrant case collections with current non-invalid database case IDs.

This script removes orphan vector points whose IDs no longer exist in the
current non-invalid PostgreSQL case set.
"""

from __future__ import annotations

from typing import Iterable

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import PointIdsList
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import settings
from src.database.models import Case


COLLECTIONS = [
    "nyaya_cases_combined",
    "nyaya_cases_factual",
    "nyaya_cases_legal",
    "nyaya_cases_fulltext",
]


def get_db_case_ids() -> set[int]:
    """Return non-invalid case IDs from database."""
    engine = create_engine(settings.database_url, echo=False)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    try:
        rows = session.query(Case.id).filter(Case.validation_status != "invalid").all()
        return {int(row[0]) for row in rows if row and row[0] is not None}
    finally:
        session.close()


def scroll_ids(client: QdrantClient, collection_name: str) -> set[int]:
    """Collect all point IDs from a Qdrant collection."""
    ids: set[int] = set()
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            limit=1000,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        for point in points:
            if point.id is not None:
                ids.add(int(point.id))
        if offset is None:
            break
    return ids


def chunks(items: list[int], chunk_size: int) -> Iterable[list[int]]:
    """Yield fixed-size chunks from list."""
    for i in range(0, len(items), chunk_size):
        yield items[i : i + chunk_size]


def main() -> None:
    """Sync vector index by deleting orphan point IDs."""
    db_ids = get_db_case_ids()
    logger.info("Loaded non-invalid DB IDs", count=len(db_ids))

    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    total_deleted = 0
    for collection_name in COLLECTIONS:
        collection_ids = scroll_ids(client, collection_name)
        orphan_ids = sorted(collection_ids - db_ids)
        if not orphan_ids:
            logger.info("No orphan vectors found", collection=collection_name)
            continue

        logger.info(
            "Deleting orphan vectors",
            collection=collection_name,
            orphan_count=len(orphan_ids),
        )

        for batch in chunks(orphan_ids, 1000):
            client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=batch),
            )
            total_deleted += len(batch)

    logger.info("Vector sync complete", total_deleted=total_deleted)


if __name__ == "__main__":
    main()
