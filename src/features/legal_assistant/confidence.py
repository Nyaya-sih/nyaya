"""Confidence estimation for legal assistant responses."""

from src.features.legal_assistant.schemas import ConfidenceBreakdown


class ConfidenceEstimator:
    """Compute deterministic confidence from retrieval support signals."""

    def estimate(
        self,
        citation_count: int,
        has_context: bool,
        avg_citation_score: float,
    ) -> ConfidenceBreakdown:
        """Estimate confidence from retrieval and citation support signals."""
        retrieval_support = min(1.0, max(0.0, avg_citation_score))
        citation_coverage = (
            0.85 if citation_count >= 3 else (0.65 if citation_count > 0 else 0.2)
        )
        context_bonus = 0.08 if has_context else 0.0
        overall = round(
            min(
                1.0,
                (retrieval_support * 0.55) + (citation_coverage * 0.45) + context_bonus,
            ),
            3,
        )

        risk_flags: list[str] = []
        if not has_context:
            risk_flags.append("insufficient_context")
        if citation_count == 0:
            risk_flags.append("no_citations")
        if avg_citation_score < 0.45:
            risk_flags.append("weak_retrieval_support")

        return ConfidenceBreakdown(
            overall=overall,
            retrieval_support=retrieval_support,
            citation_coverage=citation_coverage,
            risk_flags=risk_flags,
        )
