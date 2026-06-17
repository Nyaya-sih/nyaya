"""Citation validation helpers for legal assistant."""

from src.features.legal_assistant.retriever import EvidenceChunk


class CitationValidator:
    """Validate and normalize citations produced for an answer."""

    def validate(
        self, evidence: list[EvidenceChunk]
    ) -> tuple[list[EvidenceChunk], list[str]]:
        """Return valid evidence citations and warning messages."""
        warnings: list[str] = []
        deduped: dict[str, EvidenceChunk] = {}
        for chunk in evidence:
            if not chunk.citation_id or not chunk.excerpt.strip():
                continue
            current = deduped.get(chunk.citation_id)
            if current is None or chunk.score > current.score:
                deduped[chunk.citation_id] = chunk

        valid = sorted(deduped.values(), key=lambda x: x.score, reverse=True)
        if len(valid) < len(evidence):
            warnings.append(
                "Some evidence chunks were dropped due to invalid citation data."
            )
        if not valid:
            warnings.append("No validated citations available for this response.")
        elif max(chunk.score for chunk in valid) < 0.45:
            warnings.append("Retrieved evidence has low relevance confidence.")
        return valid, warnings
