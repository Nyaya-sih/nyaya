"""
One-time script to generate and index embeddings for all cases.

Steps:
1. Check what's already indexed in Qdrant (resume support)
2. Load all non-invalid cases from PostgreSQL that aren't yet indexed
3. Generate multi-level embeddings in batches of 50
4. Index each batch into Qdrant immediately (don't accumulate all in memory)
5. Log progress every 50 cases: count, cost so far, ETA
6. Save embedding manifest to data/processed/embedding_manifest.json

IMPORTANT: Resume support
- Before starting, check existing Qdrant index size
- Only embed cases NOT already in Qdrant (check by case ID)
- This allows re-running after failures without duplicates or extra cost

Cost estimate display before starting:
  Cases to embed: X
  Estimated cost: $X.XX
  Estimated time: ~XX minutes
  Proceed? (yes/no):

Final output:
  Cases embedded: X
  Failed: X
  Total tokens: X
  Total cost: $X.XX
  Manifest: data/processed/embedding_manifest.json
"""

import argparse
import json
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
    """Parse CLI args for embedding generation script."""
    parser = argparse.ArgumentParser(
        description="Generate multi-vector case embeddings"
    )
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
    """Generate and index embeddings for all cases."""
    args = parse_args()
    logger.info("Embedding generation started")

    openai_client = OpenAI(api_key=settings.openai_api_key)
    embedding_generator = EmbeddingGenerator(openai_client)
    vector_store = VectorStore(host=settings.qdrant_host, port=settings.qdrant_port)
    vector_store.create_collections(recreate=False)

    existing_ids = _get_existing_case_ids(vector_store)
    logger.info("Existing vectors detected", count=len(existing_ids))

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
            logger.warning("Embedding generation aborted by user")
            return

        batch_size = max(1, int(args.batch_size))
        embedded_count = 0
        failed_count = 0
        manifest = []

        start_time = time.time()
        for i in range(0, len(cases_to_embed), batch_size):
            batch_cases = cases_to_embed[i : i + batch_size]
            batch_embeddings = []
            for case in batch_cases:
                try:
                    embedding = embedding_generator.generate_case_embedding(case)
                    batch_embeddings.append(embedding)
                    manifest.append({"case_id": case.id, "status": "indexed"})
                    embedded_count += 1
                except Exception as exc:
                    logger.error("Embedding failed", case_id=case.id, error=str(exc))
                    manifest.append(
                        {"case_id": case.id, "status": "failed", "error": str(exc)}
                    )
                    failed_count += 1

            if batch_embeddings:
                vector_store.batch_index_cases(
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

        _write_manifest(manifest)
        logger.info(
            "Embedding generation complete",
            embedded=embedded_count,
            failed=failed_count,
            total_tokens=embedding_generator.total_tokens_used,
            total_cost=f"${embedding_generator.estimated_cost:.2f}",
            manifest_path="data/processed/embedding_manifest.json",
        )
    finally:
        session.close()


def _get_existing_case_ids(vector_store: VectorStore) -> set[int]:
    """Collect existing case IDs from Qdrant.

    Args:
        vector_store: VectorStore instance.

    Returns:
        Set of case IDs already indexed.
    """
    existing_ids = set()
    offset = None

    while True:
        points, offset = vector_store.client.scroll(
            collection_name=vector_store.COLLECTION_COMBINED,
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
    """Estimate average token count per case.

    Args:
        generator: EmbeddingGenerator instance.
        cases: List of Case objects.

    Returns:
        Estimated tokens per case.
    """
    sample = cases[:50] if cases else []
    if not sample:
        return 0

    total_tokens = 0
    for case in sample:
        factual_text = generator.build_factual_text(case)
        legal_text = generator.build_legal_text(case)
        outcome_text = generator.build_outcome_text(case)
        total_tokens += len(generator.encoder.encode(factual_text))
        total_tokens += len(generator.encoder.encode(legal_text))
        total_tokens += len(generator.encoder.encode(outcome_text))
    return int(total_tokens / len(sample))


def _write_manifest(entries: list[dict]) -> None:
    """Write embedding manifest to disk.

    Args:
        entries: Manifest entries.
    """
    output_path = Path("data/processed/embedding_manifest.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(entries, file, indent=2)


if __name__ == "__main__":
    main()
