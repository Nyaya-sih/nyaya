"""Index prepared legal KB chunks into Qdrant with embeddings.

Input JSONL: data/processed/legal_kb_chunks.jsonl
Output manifest: data/processed/legal_kb_embedding_manifest.json
"""

from __future__ import annotations

import argparse
import json
from hashlib import sha1
from pathlib import Path
from typing import Any

from loguru import logger
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from src.config.settings import settings
from src.features.similar_cases.embedding_generator import EmbeddingGenerator


COLLECTION_NAME = "nyaya_legal_kb"


def parse_args() -> argparse.Namespace:
    """Parse command-line args for legal KB indexing."""
    parser = argparse.ArgumentParser(description="Index legal KB chunks into Qdrant")
    parser.add_argument(
        "--input",
        type=str,
        default="data/processed/legal_kb_chunks.jsonl",
        help="Prepared KB chunks JSONL path",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default="data/processed/legal_kb_embedding_manifest.json",
        help="Output embedding manifest path",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for indexing upserts",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate target Qdrant collection before indexing",
    )
    return parser.parse_args()


def load_chunks(path: Path) -> list[dict[str, Any]]:
    """Load prepared chunk JSONL file."""
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


def ensure_collection(client: QdrantClient, recreate: bool = False) -> None:
    """Ensure legal KB collection exists with payload indexes."""
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION_NAME in existing and recreate:
        client.delete_collection(collection_name=COLLECTION_NAME)
        existing.remove(COLLECTION_NAME)

    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EmbeddingGenerator.EMBEDDING_DIM,
                distance=Distance.COSINE,
            ),
        )

    for field_name, schema in [
        ("source_type", PayloadSchemaType.KEYWORD),
        ("act_name", PayloadSchemaType.KEYWORD),
        ("section_or_article", PayloadSchemaType.KEYWORD),
        ("chapter_or_part", PayloadSchemaType.KEYWORD),
        ("is_superseded", PayloadSchemaType.BOOL),
        ("jurisdiction", PayloadSchemaType.KEYWORD),
        ("year", PayloadSchemaType.INTEGER),
    ]:
        try:
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name=field_name,
                field_schema=schema,
            )
        except Exception:
            # idempotent behavior across runs
            pass


def make_embedding_text(chunk: dict[str, Any]) -> str:
    """Compose embedding text from chunk metadata and body."""
    return "\n".join(
        [
            f"Title: {chunk.get('title', '')}",
            f"Act: {chunk.get('act_name', '')}",
            f"Unit: {chunk.get('section_or_article', '')}",
            f"Chapter: {chunk.get('chapter_or_part', '')}",
            f"Superseded: {chunk.get('is_superseded', False)}",
            chunk.get("text", ""),
        ]
    ).strip()


def chunk_point_id(chunk_id: str) -> int:
    """Map chunk ID string to deterministic positive integer point ID."""
    digest = sha1(chunk_id.encode("utf-8")).hexdigest()
    return int(digest[:15], 16)


def main() -> None:
    """Run legal KB indexing."""
    args = parse_args()
    input_path = Path(args.input)
    manifest_path = Path(args.manifest)
    chunks = load_chunks(input_path)
    if not chunks:
        logger.error("No chunks to index", input=str(input_path))
        return

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for legal KB indexing")

    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    ensure_collection(client, recreate=args.recreate)

    embedder = EmbeddingGenerator(OpenAI(api_key=settings.openai_api_key))
    manifest_rows: list[dict[str, Any]] = []
    batch_points: list[PointStruct] = []

    for row in chunks:
        chunk_id = str(row.get("chunk_id", "")).strip()
        if not chunk_id:
            manifest_rows.append(
                {"chunk_id": None, "status": "failed", "error": "missing chunk_id"}
            )
            continue

        text = make_embedding_text(row)
        try:
            vector = embedder._normalize(embedder._get_embedding(text)).tolist()
            payload = dict(row)
            payload["_point_kind"] = "legal_kb_chunk"
            point = PointStruct(
                id=chunk_point_id(chunk_id), vector=vector, payload=payload
            )
            batch_points.append(point)
            manifest_rows.append({"chunk_id": chunk_id, "status": "indexed"})
        except Exception as exc:
            manifest_rows.append(
                {"chunk_id": chunk_id, "status": "failed", "error": str(exc)}
            )

        if len(batch_points) >= args.batch_size:
            client.upsert(collection_name=COLLECTION_NAME, points=batch_points)
            batch_points = []

    if batch_points:
        client.upsert(collection_name=COLLECTION_NAME, points=batch_points)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest_rows, indent=2), encoding="utf-8")

    indexed = sum(1 for row in manifest_rows if row.get("status") == "indexed")
    failed = sum(1 for row in manifest_rows if row.get("status") == "failed")
    logger.info(
        "Legal KB indexing complete",
        collection=COLLECTION_NAME,
        indexed=indexed,
        failed=failed,
        manifest=str(manifest_path),
    )


if __name__ == "__main__":
    main()
