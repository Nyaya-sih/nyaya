"""Retriever scaffold for legal assistant."""

from dataclasses import dataclass


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
    """Placeholder retriever for iteration 0/1.

    Iteration 3 will implement multi-source retrieval from legal KB and case vectors.
    """

    def retrieve(
        self, question: str, context_text: str, top_k: int
    ) -> list[EvidenceChunk]:
        """Return contextual evidence chunks from active context only."""
        if not context_text.strip():
            return []
        excerpt = context_text[:1200]
        return [
            EvidenceChunk(
                citation_id="CTX-1",
                source_type="document",
                title="Active session context",
                act_or_case="Uploaded/selected case context",
                section_or_article=None,
                excerpt=excerpt,
                score=0.75,
            )
        ][:top_k]
