"""
Generate and index full-text-lite embeddings for all cases.

This script only creates the full-text collection vectors (single embedding per case).
It does NOT regenerate the factual/legal/outcome embeddings.
"""

import argparse
import time
from pathlib import Path

from loguru import logger
from openai import OpenAI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import settings
from src.database.models import Case
from src.features.similar_cases.embedding_generator import EmbeddingGenerator
from src.features.similar_cases.vector_store import VectorStore


def parse_args() -> argparse.Namespace:
    """Parse CLI args for full-text embedding generation script."""
    parser = argparse.ArgumentParser(description="Generate full-text-lite embeddings")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip interactive confirmation prompt",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for embedding and indexing",
    )
    return parser.parse_args()


def main() -> None:
    """Generate and index full-text-lite embeddings for all cases."""
    args = parse_args()
    logger.info("Full-text embedding generation started")

    openai_client = OpenAI(api_key=settings.openai_api_key)
    embedding_generator = EmbeddingGenerator(openai_client)
    vector_store = VectorStore(host=settings.qdrant_host, port=settings.qdrant_port)
    vector_store.create_collections(recreate=False)

    existing_ids = _get_existing_case_ids(vector_store)
    logger.info("Existing full-text vectors detected", count=len(existing_ids))

    engine = create_engine(settings.database_url, echo=False)
    session_local = sessionmaker(bind=engine)
    session = session_local()

    try:
        cases = (
            session.query(Case)
            .filter(Case.validation_status != "invalid")
            .order_by(Case.id)
            .all()
        )
        cases_to_embed = [case for case in cases if case.id not in existing_ids]
        logger.info("Cases to embed", count=len(cases_to_embed))

        estimated_tokens_per_case = _estimate_tokens_per_case(
            embedding_generator, cases_to_embed
        )
        estimated_tokens = estimated_tokens_per_case * len(cases_to_embed)
        estimated_cost = (estimated_tokens / 1_000_000) * 0.13
        estimated_time_minutes = (len(cases_to_embed) * 2) / 60

        logger.info(
            "Cost estimate",
            cases=len(cases_to_embed),
            estimated_cost=f"${estimated_cost:.2f}",
            estimated_time_minutes=f"{estimated_time_minutes:.1f}",
        )

        if not args.yes:
            proceed = input("Proceed? (yes/no): ").strip().lower()
        else:
            proceed = "yes"

        if proceed != "yes":
            logger.warning("Full-text embedding generation aborted by user")
            return

        batch_size = max(1, int(args.batch_size))
        embedded_count = 0
        failed_count = 0

        start_time = time.time()
        for i in range(0, len(cases_to_embed), batch_size):
            batch_cases = cases_to_embed[i : i + batch_size]
            batch_embeddings = []
            for case in batch_cases:
                try:
                    embedding = embedding_generator.generate_fulltext_embedding(case)
                    batch_embeddings.append(embedding)
                    embedded_count += 1
                except Exception as exc:
                    logger.error(
                        "Full-text embedding failed", case_id=case.id, error=str(exc)
                    )
                    failed_count += 1

            if batch_embeddings:
                vector_store.batch_index_fulltext(
                    batch_cases, batch_embeddings, batch_size=batch_size
                )

            elapsed = time.time() - start_time
            eta = (elapsed / max(embedded_count, 1)) * (
                len(cases_to_embed) - embedded_count
            )
            logger.info(
                "Progress",
                embedded=embedded_count,
                failed=failed_count,
                cost_so_far=f"${embedding_generator.estimated_cost:.2f}",
                eta_minutes=f"{eta / 60:.1f}",
            )
    finally:
        session.close()


def _get_existing_case_ids(vector_store: VectorStore) -> set[int]:
    """Collect existing case IDs from full-text collection."""
    existing_ids = set()
    offset = None

    while True:
        points, offset = vector_store.client.scroll(
            collection_name=vector_store.COLLECTION_FULLTEXT,
            limit=1000,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        for point in points:
            if point.id is not None:
                existing_ids.add(int(point.id))
        if offset is None:
            break
    return existing_ids


def _estimate_tokens_per_case(generator: EmbeddingGenerator, cases: list) -> int:
    """Estimate token count per case for full-text-lite embeddings."""
    sample = cases[:50] if cases else []
    if not sample:
        return 0

    total_tokens = 0
    for case in sample:
        full_text = generator.build_fulltext_text(case)
        total_tokens += len(generator.encoder.encode(full_text))
    return int(total_tokens / len(sample))


if __name__ == "__main__":
    main()
