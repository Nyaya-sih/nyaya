"""Hybrid retriever for legal assistant (context + legal KB FAISS)."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class EvidenceChunk:
    """Evidence chunk returned by retriever."""

    citation_id: str
    source_type: str
    title: str
    act_or_case: str
    section_or_article: str | None
    excerpt: str
    score: float


class AssistantRetriever:
    """Retriever that blends active context with legal-KB FAISS hits."""

    INDEX_FILE = Path("legal_kb/faiss/legal_kb.index")
    MAP_FILE = Path("legal_kb/faiss/chunk_id_map.json")
    LOOKUP_FILE = Path("legal_kb/faiss/chunk_text_lookup.json")
    MODEL_NAME = "sentence-transformers/multi-qa-mpnet-base-dot-v1"

    def __init__(self) -> None:
        self._initialized = False
        self._enabled = not bool(os.getenv("PYTEST_CURRENT_TEST"))
        self._faiss = None
        self._index = None
        self._model = None
        self._chunk_id_map: list[dict[str, Any]] = []
        self._chunk_text_lookup: dict[str, str] = {}

    def _lazy_init(self) -> None:
        if self._initialized or not self._enabled:
            return
        self._initialized = True
        try:
            import faiss  # type: ignore
            from sentence_transformers import SentenceTransformer

            if (
                not self.INDEX_FILE.exists()
                or not self.MAP_FILE.exists()
                or not self.LOOKUP_FILE.exists()
            ):
                self._enabled = False
                return

            self._faiss = faiss
            self._index = faiss.read_index(str(self.INDEX_FILE))
            self._chunk_id_map = json.loads(self.MAP_FILE.read_text(encoding="utf-8"))
            self._chunk_text_lookup = json.loads(
                self.LOOKUP_FILE.read_text(encoding="utf-8")
            )
            self._model = SentenceTransformer(self.MODEL_NAME)
        except Exception:
            self._enabled = False

    @staticmethod
    def _normalize_score(raw_score: float) -> float:
        # cosine-ish score in [-1, 1] -> [0, 1]
        score = (float(raw_score) + 1.0) / 2.0
        return max(0.0, min(1.0, score))

    @staticmethod
    def _source_type(meta_type: str) -> str:
        lowered = (meta_type or "").lower()
        if lowered in {"constitution", "statute"}:
            return lowered
        if lowered in {"court_rule", "procedural_rule", "secondary_source"}:
            return "other"
        return "other"

    def _context_evidence(self, context_text: str) -> list[EvidenceChunk]:
        if not context_text.strip():
            return []
        return [
            EvidenceChunk(
                citation_id="CTX-1",
                source_type="document",
                title="Active session context",
                act_or_case="Uploaded/selected case context",
                section_or_article=None,
                excerpt=context_text[:1200],
                score=0.75,
            )
        ]

    def _semantic_hits(
        self,
        question: str,
        top_k: int,
        statutes_hint: list[str],
        sections_hint: list[str],
    ) -> list[EvidenceChunk]:
        if not self._enabled:
            return []

        self._lazy_init()
        if not self._enabled or self._model is None or self._index is None:
            return []

        query_vec = self._model.encode(
            [question], convert_to_numpy=True, show_progress_bar=False
        ).astype(np.float32)
        self._faiss.normalize_L2(query_vec)
        scores, idxs = self._index.search(query_vec, max(top_k * 4, 20))

        hints = {h.lower() for h in statutes_hint}
        sec_hints = {s.lower().replace("sec.", "section") for s in sections_hint}

        evidence: list[EvidenceChunk] = []
        seen_ids: set[str] = set()
        for raw_score, idx in zip(scores[0], idxs[0]):
            if idx < 0 or idx >= len(self._chunk_id_map):
                continue
            meta = self._chunk_id_map[idx]
            cid = str(meta.get("chunk_id") or "")
            if not cid or cid in seen_ids:
                continue

            text = self._chunk_text_lookup.get(cid, "")
            if not text:
                continue

            score = self._normalize_score(float(raw_score))

            act_name = str(meta.get("act_name") or "")
            section = str(meta.get("section_or_article") or "")
            section_norm = section.lower()
            act_norm = act_name.lower()
            lexical_bonus = 0.0
            if hints and any(h in act_norm for h in hints):
                lexical_bonus += 0.08
            if sec_hints and any(h in section_norm for h in sec_hints):
                lexical_bonus += 0.08
            score = max(0.0, min(1.0, score + lexical_bonus))

            evidence.append(
                EvidenceChunk(
                    citation_id=cid,
                    source_type=self._source_type(str(meta.get("source_type") or "")),
                    title=str(meta.get("section_title") or act_name),
                    act_or_case=act_name,
                    section_or_article=section or None,
                    excerpt=text[:1200],
                    score=score,
                )
            )
            seen_ids.add(cid)
            if len(evidence) >= top_k:
                break

        evidence.sort(key=lambda x: x.score, reverse=True)
        return evidence[:top_k]

    def retrieve(
        self,
        question: str,
        context_text: str,
        top_k: int,
        statutes_hint: list[str] | None = None,
        sections_hint: list[str] | None = None,
    ) -> list[EvidenceChunk]:
        """Return blended evidence chunks from context and legal KB."""
        statutes_hint = statutes_hint or []
        sections_hint = sections_hint or []

        semantic = self._semantic_hits(
            question=question,
            top_k=max(1, top_k - 1),
            statutes_hint=statutes_hint,
            sections_hint=sections_hint,
        )
        context = self._context_evidence(context_text)

        blended = semantic + context
        blended.sort(key=lambda x: x.score, reverse=True)
        return blended[:top_k]
