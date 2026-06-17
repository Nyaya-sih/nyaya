"""Context builder for legal assistant answers."""

from src.features.legal_assistant.retriever import EvidenceChunk


class ContextBuilder:
    """Builds bounded model context from evidence chunks."""

    def build(
        self, question: str, evidence: list[EvidenceChunk], max_chars: int = 8000
    ) -> str:
        """Build textual context payload for answer generation."""
        parts = [f"Question: {question}"]
        used = len(parts[0])
        for idx, chunk in enumerate(evidence, start=1):
            block = (
                f"\n\n[{idx}] citation_id={chunk.citation_id}"
                f" source={chunk.source_type}"
                f" score={chunk.score:.2f}\n"
                f"act_or_case={chunk.act_or_case}"
                f" section_or_article={chunk.section_or_article or 'n/a'}\n"
                f"{chunk.excerpt}"
            )
            if used + len(block) > max_chars:
                break
            parts.append(block)
            used += len(block)
        return "".join(parts)
