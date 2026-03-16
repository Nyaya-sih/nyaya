"""
Qdrant vector store for NyayaAI.

Four collections:
- nyaya_cases_combined: primary search
- nyaya_cases_factual: factual-only search
- nyaya_cases_legal: legal/statutory search
- nyaya_cases_fulltext: full-text-lite search

Each point payload contains full case metadata for filtering.
"""

from dataclasses import dataclass
from typing import Optional, Any

import numpy as np
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    Range,
    PayloadSchemaType,
)
from tqdm import tqdm


@dataclass
class SearchResult:
    """Vector search result wrapper."""

    case_id: int
    case_title: str
    court: str
    date_of_judgment: str
    case_type: str
    verdict: str
    similarity_score: float
    payload: dict


class VectorStore:
    """Qdrant vector store client for similar case retrieval."""

    COLLECTION_COMBINED = "nyaya_cases_combined"
    COLLECTION_FACTUAL = "nyaya_cases_factual"
    COLLECTION_LEGAL = "nyaya_cases_legal"
    COLLECTION_FULLTEXT = "nyaya_cases_fulltext"
    VECTOR_DIM = 3072

    def __init__(self, host: str = "localhost", port: int = 6333) -> None:
        """Initialize Qdrant client.

        Args:
            host: Qdrant host.
            port: Qdrant port.
        """
        self.client = QdrantClient(host=host, port=port)

    def create_collections(self, recreate: bool = False) -> None:
        """Create all collections with COSINE distance.

        Create payload indexes for: court, case_type, verdict, year.
        Skip if collection exists and recreate=False.

        Args:
            recreate: Whether to recreate collections if they exist.
        """
        collections = [
            self.COLLECTION_COMBINED,
            self.COLLECTION_FACTUAL,
            self.COLLECTION_LEGAL,
            self.COLLECTION_FULLTEXT,
        ]

        existing = {c.name for c in self.client.get_collections().collections}
        for name in collections:
            if name in existing and not recreate:
                logger.info("Collection already exists", collection=name)
                continue

            if name in existing and recreate:
                logger.warning("Recreating collection", collection=name)
                self.client.delete_collection(collection_name=name)

            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=self.VECTOR_DIM, distance=Distance.COSINE
                ),
            )
            self._create_payload_indexes(name)
            logger.info("Collection created", collection=name)

    def _build_payload(self, case: Any) -> dict:
        """Build Qdrant payload from SQLAlchemy case object.

        Include all metadata fields needed for filtering and display.
        Handle None values gracefully.

        Args:
            case: SQLAlchemy Case instance.

        Returns:
            Payload dictionary.
        """
        date_of_judgment = getattr(case, "date_of_judgment", None)
        year = date_of_judgment.year if date_of_judgment else None

        statutes = self._get_statute_names(case)
        payload = {
            "case_id": getattr(case, "id", None),
            "case_title": getattr(case, "case_title", "") or "",
            "court": getattr(case, "court", "") or "",
            "date_of_judgment": date_of_judgment.isoformat()
            if date_of_judgment
            else "",
            "year": year,
            "case_type": getattr(case, "case_type", "") or "",
            "verdict": getattr(case, "verdict", "") or "",
            "statutes_cited": statutes,
            "sections_invoked": list(getattr(case, "sections_invoked", []) or []),
            "charges": list(getattr(case, "charges", []) or []),
            "key_arguments_petitioner": getattr(case, "key_arguments_petitioner", "")
            or "",
            "key_arguments_respondent": getattr(case, "key_arguments_respondent", "")
            or "",
            "court_reasoning": getattr(case, "court_reasoning", "") or "",
            "headnotes": list(getattr(case, "headnotes", []) or []),
            "full_text": getattr(case, "full_text", "") or "",
            "average_confidence": getattr(case, "average_confidence", None),
            "validation_status": getattr(case, "validation_status", "") or "",
            "source_file_path": getattr(case, "source_file_path", "") or "",
        }

        precedents = []
        for precedent in getattr(case, "precedents", []) or []:
            precedents.append(
                {
                    "case_name": getattr(precedent, "case_name", None),
                    "citation": getattr(precedent, "citation", None),
                    "year": getattr(precedent, "year", None),
                    "court": getattr(precedent, "court", None),
                    "legal_principle": getattr(precedent, "legal_principle", None),
                }
            )
        payload["precedents_cited"] = precedents

        return payload

    def _get_statute_names(self, case: Any) -> list[str]:
        """Extract statute names from a case.

        Args:
            case: SQLAlchemy Case instance.

        Returns:
            List of statute names.
        """
        statutes = []
        case_statutes = getattr(case, "statutes", None)
        if case_statutes:
            for statute in case_statutes:
                name = getattr(statute, "statute_name", None)
                if name:
                    statutes.append(name)

        fallback = getattr(case, "statutes_cited", None)
        if fallback:
            for item in fallback:
                if item:
                    statutes.append(str(item))

        return list(dict.fromkeys(statutes))

    def batch_index_cases(
        self, cases: list, embeddings: list, batch_size: int = 100
    ) -> None:
        """Index cases into core collections in batches.

        Show tqdm progress bar.

        Args:
            cases: List of Case objects.
            embeddings: List of CaseEmbedding objects.
            batch_size: Batch size for indexing.
        """
        total = len(cases)
        if total == 0:
            logger.warning("No cases provided for indexing")
            return

        for i in tqdm(range(0, total, batch_size), desc="Indexing cases"):
            batch_cases = cases[i : i + batch_size]
            batch_embeddings = embeddings[i : i + batch_size]

            combined_points = []
            factual_points = []
            legal_points = []

            for case, embedding in zip(batch_cases, batch_embeddings):
                payload = self._build_payload(case)
                point_id = payload.get("case_id")
                if point_id is None:
                    continue
                point_id = int(point_id)

                combined_points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding.combined_embedding.tolist(),
                        payload=payload,
                    )
                )
                factual_points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding.factual_embedding.tolist(),
                        payload=payload,
                    )
                )
                legal_points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding.legal_embedding.tolist(),
                        payload=payload,
                    )
                )

            try:
                self.client.upsert(
                    collection_name=self.COLLECTION_COMBINED, points=combined_points
                )
                self.client.upsert(
                    collection_name=self.COLLECTION_FACTUAL, points=factual_points
                )
                self.client.upsert(
                    collection_name=self.COLLECTION_LEGAL, points=legal_points
                )
            except Exception as exc:
                logger.error("Batch upsert failed", error=str(exc))

    def batch_index_fulltext(
        self, cases: list, embeddings: list, batch_size: int = 100
    ) -> None:
        """Index cases into full-text-lite collection in batches."""
        total = len(cases)
        if total == 0:
            logger.warning("No cases provided for full-text indexing")
            return

        for i in tqdm(range(0, total, batch_size), desc="Indexing full-text cases"):
            batch_cases = cases[i : i + batch_size]
            batch_embeddings = embeddings[i : i + batch_size]

            points = []
            for case, embedding in zip(batch_cases, batch_embeddings):
                payload = self._build_payload(case)
                point_id = payload.get("case_id")
                if point_id is None:
                    continue
                point_id = int(point_id)
                points.append(
                    PointStruct(id=point_id, vector=embedding.tolist(), payload=payload)
                )

            try:
                self.client.upsert(
                    collection_name=self.COLLECTION_FULLTEXT, points=points
                )
            except Exception as exc:
                logger.error("Full-text batch upsert failed", error=str(exc))

    def collection_exists(self, name: str) -> bool:
        """Check if a collection exists in Qdrant."""
        existing = {c.name for c in self.client.get_collections().collections}
        return name in existing

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 50,
        court_filter: Optional[str] = None,
        case_type_filter: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        verdict_filter: Optional[str] = None,
        collection: Optional[str] = None,
        exclude_case_id: Optional[int] = None,
    ) -> list[SearchResult]:
        """Search for similar cases with optional filters.

        Build Qdrant Filter from provided filter params.
        Exclude the query case from results if exclude_case_id provided.

        Args:
            query_embedding: Query embedding vector.
            top_k: Number of results to return.
            court_filter: Court name filter.
            case_type_filter: Case type filter.
            year_from: Minimum year.
            year_to: Maximum year.
            verdict_filter: Verdict filter.
            collection: Qdrant collection name.
            exclude_case_id: Case ID to exclude.

        Returns:
            List of SearchResult objects.
        """
        must_conditions = []
        if court_filter:
            must_conditions.append(
                FieldCondition(key="court", match=MatchValue(value=court_filter))
            )
        if case_type_filter:
            must_conditions.append(
                FieldCondition(
                    key="case_type", match=MatchValue(value=case_type_filter)
                )
            )
        if verdict_filter:
            must_conditions.append(
                FieldCondition(key="verdict", match=MatchValue(value=verdict_filter))
            )
        if year_from is not None or year_to is not None:
            must_conditions.append(
                FieldCondition(key="year", range=Range(gte=year_from, lte=year_to))
            )

        must_not_conditions = []
        if exclude_case_id is not None:
            must_not_conditions.append(
                FieldCondition(key="case_id", match=MatchValue(value=exclude_case_id))
            )

        filter_payload = None
        if must_conditions or must_not_conditions:
            filter_payload = Filter(
                must=must_conditions or None, must_not=must_not_conditions or None
            )

        collection_name = collection or self.COLLECTION_COMBINED
        search_kwargs = {
            "collection_name": collection_name,
            "query_vector": query_embedding.tolist(),
            "limit": top_k,
            "query_filter": filter_payload,
        }
        try:
            results = self.client.search(with_payload=True, **search_kwargs)
        except TypeError:
            # Backward compatibility for test doubles / older clients
            results = self.client.search(**search_kwargs)

        output = []
        for point in results:
            payload = point.payload or {}
            case_id = payload.get("case_id")
            if case_id is None:
                continue
            case_id = int(case_id)
            output.append(
                SearchResult(
                    case_id=case_id,
                    case_title=payload.get("case_title", ""),
                    court=payload.get("court", ""),
                    date_of_judgment=payload.get("date_of_judgment", ""),
                    case_type=payload.get("case_type", ""),
                    verdict=payload.get("verdict", ""),
                    similarity_score=point.score,
                    payload=payload,
                )
            )

        return output

    def search_across_collections(
        self,
        query_embedding: np.ndarray,
        collections: list[str],
        top_k_each: int,
        court_filter: Optional[str] = None,
        case_type_filter: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        verdict_filter: Optional[str] = None,
        exclude_case_id: Optional[int] = None,
    ) -> list[SearchResult]:
        """Search multiple collections and return deduplicated best hits.

        Keeps the highest vector score per case_id across collections.
        """
        best_by_case: dict[int, SearchResult] = {}
        for collection in collections:
            try:
                hits = self.search(
                    query_embedding=query_embedding,
                    top_k=top_k_each,
                    court_filter=court_filter,
                    case_type_filter=case_type_filter,
                    year_from=year_from,
                    year_to=year_to,
                    verdict_filter=verdict_filter,
                    collection=collection,
                    exclude_case_id=exclude_case_id,
                )
            except Exception as exc:
                logger.warning(
                    "Cross-collection search failed",
                    collection=collection,
                    error=str(exc),
                )
                continue

            for hit in hits:
                existing = best_by_case.get(hit.case_id)
                if existing is None or hit.similarity_score > existing.similarity_score:
                    best_by_case[hit.case_id] = hit

        merged = sorted(
            best_by_case.values(), key=lambda item: item.similarity_score, reverse=True
        )
        return merged

    def get_collection_stats(self) -> dict:
        """Return vectors_count and points_count for all collections."""
        stats = {}
        for name in [
            self.COLLECTION_COMBINED,
            self.COLLECTION_FACTUAL,
            self.COLLECTION_LEGAL,
            self.COLLECTION_FULLTEXT,
        ]:
            info = self.client.get_collection(collection_name=name)
            stats[name] = {
                "indexed_vectors_count": getattr(
                    info,
                    "indexed_vectors_count",
                    getattr(info, "vectors_count", None),
                ),
                "points_count": info.points_count,
            }
        return stats

    def _create_payload_indexes(self, collection_name: str) -> None:
        """Create payload indexes for common filter fields.

        Args:
            collection_name: Qdrant collection name.
        """
        indexes = {
            "court": PayloadSchemaType.KEYWORD,
            "case_type": PayloadSchemaType.KEYWORD,
            "verdict": PayloadSchemaType.KEYWORD,
            "year": PayloadSchemaType.INTEGER,
        }
        for field_name, field_type in indexes.items():
            self.client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_type,
            )
            logger.info(
                "Payload index created", collection=collection_name, field=field_name
            )
