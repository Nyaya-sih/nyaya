"""Confidence estimation for legal assistant responses."""

from src.features.legal_assistant.schemas import ConfidenceBreakdown


class ConfidenceEstimator:
    """Compute deterministic confidence from retrieval support signals."""

    def estimate(self, citation_count: int, has_context: bool) -> ConfidenceBreakdown:
        """Estimate confidence for iteration 0/1 implementation."""
        retrieval_support = 0.75 if has_context else 0.25
        citation_coverage = 0.8 if citation_count > 0 else 0.2
        overall = round((retrieval_support * 0.6) + (citation_coverage * 0.4), 3)

        risk_flags: list[str] = []
        if not has_context:
            risk_flags.append("insufficient_context")
        if citation_count == 0:
            risk_flags.append("no_citations")

        return ConfidenceBreakdown(
            overall=overall,
            retrieval_support=retrieval_support,
            citation_coverage=citation_coverage,
            risk_flags=risk_flags,
        )
