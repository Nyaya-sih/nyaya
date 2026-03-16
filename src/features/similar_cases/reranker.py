"""
Cross-encoder reranker.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2
Pipeline: top-50 from vector search -> reranked top-10

Combined score = 0.3 * vector_score + 0.7 * normalized_rerank_score
"""

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
from loguru import logger
from src.config.settings import settings

# Optional import for sentence-transformers (not needed if reranking is disabled)
try:
    from sentence_transformers import CrossEncoder

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    CrossEncoder = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False


@dataclass
class RankedResult:
    """Reranked result wrapper."""

    case_id: int
    case_title: str
    court: str
    date_of_judgment: str
    case_type: str
    verdict: str
    rerank_score: float
    vector_score: float
    combined_score: float
    payload: dict


class CrossEncoderReranker:
    """Cross-encoder reranker for top candidates."""

    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    DEFAULT_VECTOR_WEIGHT = 0.3
    DEFAULT_RERANK_WEIGHT = 0.7

    def __init__(self) -> None:
        """Load cross-encoder model on init. Log loading status."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install with: pip install sentence-transformers"
            )
        if CrossEncoder is None:
            raise ImportError("CrossEncoder is unavailable")
        model_name = settings.reranker_model_name or self.MODEL_NAME
        logger.info("Loading cross-encoder model", model=model_name)
        self.model = CrossEncoder(model_name)
        vector_weight = float(settings.reranker_vector_weight)
        rerank_weight = float(settings.reranker_model_weight)
        total_weight = vector_weight + rerank_weight
        if total_weight <= 0:
            logger.warning(
                "Invalid reranker weights configured; falling back to defaults",
                vector_weight=vector_weight,
                rerank_weight=rerank_weight,
            )
            vector_weight = self.DEFAULT_VECTOR_WEIGHT
            rerank_weight = self.DEFAULT_RERANK_WEIGHT
            total_weight = vector_weight + rerank_weight

        self.vector_weight = vector_weight / total_weight
        self.rerank_weight = rerank_weight / total_weight
        logger.info("Cross-encoder model loaded", model=model_name)

    def _build_query_text(self, query_text: str) -> str:
        """Truncate query to first 1000 chars for cross-encoder.

        Args:
            query_text: Raw query text.

        Returns:
            Truncated query text.
        """
        legal_markers = []
        lowered = query_text.lower()
        if "section" in lowered or "ipc" in lowered or "crpc" in lowered:
            legal_markers.append("legal_sections_present")
        if "petitioner" in lowered or "respondent" in lowered:
            legal_markers.append("parties_present")
        if "court" in lowered or "judgment" in lowered:
            legal_markers.append("judgment_context")

        prefix = f"[Legal Query: {', '.join(legal_markers)}] " if legal_markers else ""
        return (prefix + query_text)[:900]

    def _build_candidate_text(self, candidate: dict) -> str:
        """Build candidate text from payload.

        Include: case_title, case_type, key_arguments_petitioner[:300],
                 court_reasoning[:300], verdict
        Join with ' | ', cap at 800 chars.

        Args:
            candidate: Payload dictionary.

        Returns:
            Candidate text string.
        """
        parts = []
        case_title = candidate.get("case_title")
        if case_title:
            parts.append(f"{case_title}")

        case_type = candidate.get("case_type")
        if case_type:
            parts.append(f"Type: {case_type}")

        headnotes = candidate.get("headnotes") or []
        if headnotes:
            parts.append(f"Headnotes: {'; '.join(headnotes[:3])}")

        statutes = candidate.get("statutes_cited") or []
        if statutes:
            parts.append(f"Statutes: {', '.join(statutes[:6])}")

        sections = candidate.get("sections_invoked") or []
        if sections:
            parts.append(f"Sections: {', '.join(sections[:8])}")

        key_args = candidate.get("key_arguments_petitioner") or ""
        if key_args:
            parts.append(f"Petitioner Arguments: {key_args[:220]}")

        respondent_args = candidate.get("key_arguments_respondent") or ""
        if respondent_args:
            parts.append(f"Respondent Arguments: {respondent_args[:160]}")

        reasoning = candidate.get("court_reasoning") or ""
        if reasoning:
            parts.append(f"Court Reasoning: {reasoning[:250]}")

        verdict = candidate.get("verdict")
        if verdict:
            parts.append(f"Verdict: {verdict}")

        full_text = candidate.get("full_text") or ""
        if full_text:
            parts.append(f"Judgment Excerpt: {full_text[:220]}")

        text = " | ".join(parts)
        return text[:780]

    def rerank(
        self, query_text: str, candidates: list, top_k: int = 10
    ) -> list[RankedResult]:
        """Rerank candidates using cross-encoder.

        Normalize scores to 0-1 range.
        Combine with vector scores.
        Sort by combined_score descending.
        Return top_k results.

        Args:
            query_text: Query text.
            candidates: List of SearchResult objects.
            top_k: Number of results to return.

        Returns:
            List of RankedResult objects.
        """
        if not candidates:
            return []

        query = self._build_query_text(query_text)
        pairs = []
        for candidate in candidates:
            candidate_text = self._build_candidate_text(candidate.payload)
            pairs.append((query, candidate_text))

        scores = self.model.predict(pairs)
        scores = np.array(scores, dtype=np.float32)
        min_score = float(scores.min())
        max_score = float(scores.max())
        if max_score == min_score:
            normalized = np.full_like(scores, 0.5, dtype=np.float32)
        else:
            normalized = (scores - min_score) / (max_score - min_score)

        ranked = []
        for candidate, rerank_score in zip(candidates, normalized):
            combined = self.vector_weight * float(
                candidate.similarity_score
            ) + self.rerank_weight * float(rerank_score)
            ranked.append(
                RankedResult(
                    case_id=candidate.case_id,
                    case_title=candidate.case_title,
                    court=candidate.court,
                    date_of_judgment=candidate.date_of_judgment,
                    case_type=candidate.case_type,
                    verdict=candidate.verdict,
                    rerank_score=float(rerank_score),
                    vector_score=float(candidate.similarity_score),
                    combined_score=float(combined),
                    payload=candidate.payload,
                )
            )

        ranked.sort(
            key=lambda item: (
                -item.combined_score,
                -item.rerank_score,
                -item.vector_score,
                item.case_id,
            )
        )
        return ranked[:top_k]
