"""Citation validation helpers for legal assistant."""

from src.features.legal_assistant.retriever import EvidenceChunk


class CitationValidator:
    """Validate and normalize citations produced for an answer."""

    def validate(
        self, evidence: list[EvidenceChunk]
    ) -> tuple[list[EvidenceChunk], list[str]]:
        """Return valid evidence citations and warning messages."""
        warnings: list[str] = []
        valid = [
            chunk for chunk in evidence if chunk.citation_id and chunk.excerpt.strip()
        ]
        if len(valid) < len(evidence):
            warnings.append(
                "Some evidence chunks were dropped due to invalid citation data."
            )
        if not valid:
            warnings.append("No validated citations available for this response.")
        return valid, warnings
