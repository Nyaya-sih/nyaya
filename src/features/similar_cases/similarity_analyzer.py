"""
Rule-based similarity analyzer.

Computes similarity across 5 dimensions:
1. Statutory (30%): Overlap of statutes_cited + sections_invoked
2. Case Type (20%): Same criminal/civil/writ etc.
3. Court (15%): Same court or different
4. Outcome (20%): Same verdict category (acquit/convict/dismiss/allow/bail)
5. Temporal (15%): Proximity of judgment years

Also generates LLM explanations on-demand (not for every result).
"""

from dataclasses import dataclass
from typing import Optional

from loguru import logger
from openai import OpenAI


@dataclass
class SimilarityDimension:
    """Similarity dimension scoring."""

    name: str
    score: float
    reason: str


@dataclass
class SimilarityExplanation:
    """Structured similarity explanation."""

    overall_score: float
    dimensions: list[SimilarityDimension]
    common_statutes: list[str]
    common_case_type: bool
    common_court: bool
    verdict_match: bool
    short_explanation: str
    detailed_explanation: str


class SimilarityAnalyzer:
    """Compute rule-based similarity and optional LLM explanations."""

    def __init__(self, llm_client: Optional[OpenAI] = None) -> None:
        """Initialize the analyzer.

        Args:
            llm_client: Optional OpenAI client for LLM explanations.
        """
        self.llm_client = llm_client

    def compute_rule_based_similarity(
        self,
        query_payload: dict,
        candidate_payload: dict,
        vector_score: float
    ) -> SimilarityExplanation:
        """Compute rule-based similarity across 5 dimensions.

        Statutory: Jaccard similarity of (statutes_cited U sections_invoked)
        Case Type: Exact match = 1.0, partial = 0.5, no match = 0.0
        Court: Same = 1.0, different = 0.5
        Outcome: Map verdict to category, same category = 1.0
                 Categories: acquit, convict, dismiss, allow, bail, remand
        Temporal: max(0, 1 - abs(year_diff) / 10)

        Overall = 0.5 * vector_score + 0.5 * weighted_dimension_score

        short_explanation: 1-2 sentences, e.g.:
          "Similar because both involve IPC Section 302; both are Criminal cases."

        detailed_explanation: Markdown with star ratings per dimension.

        Args:
            query_payload: Query metadata payload.
            candidate_payload: Candidate payload from vector store.
            vector_score: Vector similarity score.

        Returns:
            SimilarityExplanation object.
        """
        query_statutes = set((query_payload.get("statutes_cited") or []) + (query_payload.get("sections_invoked") or []))
        candidate_statutes = set((candidate_payload.get("statutes_cited") or []) + (candidate_payload.get("sections_invoked") or []))

        statutory_score, common_statutes = self._jaccard_score(query_statutes, candidate_statutes)
        statutory_dim = SimilarityDimension(
            name="Statutory",
            score=statutory_score,
            reason=self._statutory_reason(common_statutes)
        )

        query_case_type = (query_payload.get("case_type") or "").strip()
        candidate_case_type = (candidate_payload.get("case_type") or "").strip()
        case_type_score = self._case_type_score(query_case_type, candidate_case_type)
        case_type_dim = SimilarityDimension(
            name="Case Type",
            score=case_type_score,
            reason=self._case_type_reason(query_case_type, candidate_case_type)
        )

        query_court = (query_payload.get("court") or "").strip()
        candidate_court = (candidate_payload.get("court") or "").strip()
        court_score = self._court_similarity(query_court, candidate_court)
        court_dim = SimilarityDimension(
            name="Court",
            score=court_score,
            reason=self._court_reason(query_court, candidate_court)
        )

        query_verdict = (query_payload.get("verdict") or "").strip()
        candidate_verdict = (candidate_payload.get("verdict") or "").strip()
        verdict_match = self._verdict_category(query_verdict) == self._verdict_category(candidate_verdict)
        outcome_score = 1.0 if verdict_match and query_verdict and candidate_verdict else 0.0
        outcome_dim = SimilarityDimension(
            name="Outcome",
            score=outcome_score,
            reason=self._outcome_reason(query_verdict, candidate_verdict)
        )

        query_year = query_payload.get("year")
        candidate_year = candidate_payload.get("year")
        temporal_score = self._temporal_score(query_year, candidate_year)
        temporal_dim = SimilarityDimension(
            name="Temporal",
            score=temporal_score,
            reason=self._temporal_reason(query_year, candidate_year)
        )

        weights = {
            "Statutory": 0.30,
            "Case Type": 0.20,
            "Court": 0.15,
            "Outcome": 0.20,
            "Temporal": 0.15,
        }
        weighted_dimension_score = (
            statutory_dim.score * weights["Statutory"]
            + case_type_dim.score * weights["Case Type"]
            + court_dim.score * weights["Court"]
            + outcome_dim.score * weights["Outcome"]
            + temporal_dim.score * weights["Temporal"]
        )

        overall_score = 0.5 * float(vector_score) + 0.5 * float(weighted_dimension_score)
        short_explanation = self._short_explanation(common_statutes, query_case_type, candidate_case_type, query_court, candidate_court)
        detailed_explanation = self._detailed_explanation([
            statutory_dim,
            case_type_dim,
            court_dim,
            outcome_dim,
            temporal_dim,
        ])

        return SimilarityExplanation(
            overall_score=overall_score,
            dimensions=[statutory_dim, case_type_dim, court_dim, outcome_dim, temporal_dim],
            common_statutes=sorted(list(common_statutes)),
            common_case_type=query_case_type.lower() == candidate_case_type.lower() if query_case_type and candidate_case_type else False,
            common_court=query_court == candidate_court if query_court and candidate_court else False,
            verdict_match=verdict_match,
            short_explanation=short_explanation,
            detailed_explanation=detailed_explanation,
        )

    def generate_llm_explanation(
        self,
        query_case_text: str,
        candidate_payload: dict,
        similarity_score: float
    ) -> str:
        """On-demand LLM explanation for a specific case pair.

        Prompt should ask for 3-4 sentence legal analysis covering:
        1. Why this case is legally relevant
        2. How legal principles/statutes overlap
        3. How advocate might use this precedent
        4. Important differences to note

        Model: gpt-4o-mini, temperature: 0.2, max_tokens: 400
        Return error string gracefully if LLM call fails.

        Args:
            query_case_text: Query case text.
            candidate_payload: Candidate payload.
            similarity_score: Similarity score for context.

        Returns:
            Generated explanation string.
        """
        if not self.llm_client:
            return "LLM explanation is not enabled."

        prompt = (
            "You are a legal research assistant for Indian court judgments. "
            "Provide a 3-4 sentence analysis comparing the query case to the candidate case. "
            "Cover: legal relevance, overlapping statutes/principles, how an advocate might use this precedent, "
            "and key differences to note."
        )

        candidate_summary = (
            f"Candidate Case Title: {candidate_payload.get('case_title', '')}\n"
            f"Court: {candidate_payload.get('court', '')}\n"
            f"Case Type: {candidate_payload.get('case_type', '')}\n"
            f"Verdict: {candidate_payload.get('verdict', '')}\n"
            f"Statutes: {', '.join(candidate_payload.get('statutes_cited', []) or [])}\n"
            f"Sections: {', '.join(candidate_payload.get('sections_invoked', []) or [])}\n"
            f"Similarity Score: {similarity_score:.2f}"
        )

        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Query Case Text:\n{query_case_text}\n\n{candidate_summary}"},
                ],
                temperature=0.2,
                max_tokens=400,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.error("LLM explanation failed", error=str(exc))
            return "LLM explanation failed. Please try again later."

    def _jaccard_score(self, a: set, b: set) -> tuple[float, set]:
        """Compute Jaccard similarity and common set."""
        if not a and not b:
            return 0.0, set()
        intersection = a.intersection(b)
        union = a.union(b)
        return len(intersection) / max(len(union), 1), intersection

    def _case_type_score(self, query_type: str, candidate_type: str) -> float:
        """Compute case type similarity score."""
        if not query_type or not candidate_type:
            return 0.0
        if query_type.lower() == candidate_type.lower():
            return 1.0
        if query_type.lower() in candidate_type.lower() or candidate_type.lower() in query_type.lower():
            return 0.5
        return 0.0

    def _case_type_reason(self, query_type: str, candidate_type: str) -> str:
        """Build case type reasoning string."""
        if not query_type or not candidate_type:
            return "Case type not specified for comparison."
        if query_type.lower() == candidate_type.lower():
            return f"Both cases are {query_type}."
        return f"Query is {query_type}, candidate is {candidate_type}."

    def _court_reason(self, query_court: str, candidate_court: str) -> str:
        """Build court reasoning string."""
        if not query_court or not candidate_court:
            return "Court not specified for comparison."
        query_tokens = self._normalize_court_name(query_court)
        candidate_tokens = self._normalize_court_name(candidate_court)
        if query_tokens == candidate_tokens and query_tokens:
            return f"Both cases were decided by {query_court}."
        overlap = query_tokens.intersection(candidate_tokens)
        if overlap:
            return f"Courts share keywords: {', '.join(sorted(overlap))}."
        return f"Different courts: {query_court} vs {candidate_court}."

    def _court_similarity(self, query_court: str, candidate_court: str) -> float:
        """Compute court similarity based on token overlap."""
        if not query_court or not candidate_court:
            return 0.0
        query_tokens = self._normalize_court_name(query_court)
        candidate_tokens = self._normalize_court_name(candidate_court)
        if not query_tokens or not candidate_tokens:
            return 0.0
        if query_tokens == candidate_tokens:
            return 1.0
        overlap_ratio = len(query_tokens.intersection(candidate_tokens)) / max(
            len(query_tokens.union(candidate_tokens)), 1
        )
        if overlap_ratio >= 0.6:
            return 0.75
        if overlap_ratio >= 0.3:
            return 0.35
        return 0.0

    def _normalize_court_name(self, court_name: str) -> set[str]:
        """Normalize court name to tokens for comparison."""
        import re

        cleaned = court_name.lower().replace("&", "and")
        cleaned = re.sub(r"[^a-z\s]", " ", cleaned)
        tokens = [token for token in cleaned.split() if token]
        stopwords = {
            "high",
            "court",
            "of",
            "judicature",
            "at",
            "bench",
            "and",
            "the",
            "for",
        }
        return {token for token in tokens if token not in stopwords}

    def _verdict_category(self, verdict: str) -> str:
        """Map verdict text to normalized category."""
        verdict_lower = verdict.lower()
        if any(term in verdict_lower for term in ["acquit", "acquitted"]):
            return "acquit"
        if any(term in verdict_lower for term in ["convict", "convicted"]):
            return "convict"
        if any(term in verdict_lower for term in ["dismiss", "dismissed"]):
            return "dismiss"
        if any(term in verdict_lower for term in ["allow", "allowed"]):
            return "allow"
        if any(term in verdict_lower for term in ["bail", "granted bail"]):
            return "bail"
        if any(term in verdict_lower for term in ["remand", "remanded"]):
            return "remand"
        return "unknown"

    def _outcome_reason(self, query_verdict: str, candidate_verdict: str) -> str:
        """Build outcome reasoning string."""
        if not query_verdict or not candidate_verdict:
            return "Outcome not specified for comparison."
        if self._verdict_category(query_verdict) == self._verdict_category(candidate_verdict):
            return f"Both cases fall under similar outcome category ({candidate_verdict})."
        return f"Different outcomes: {query_verdict} vs {candidate_verdict}."

    def _temporal_score(self, query_year: Optional[int], candidate_year: Optional[int]) -> float:
        """Compute temporal proximity score."""
        if not query_year or not candidate_year:
            return 0.0
        year_diff = abs(int(query_year) - int(candidate_year))
        return max(0.0, 1.0 - (year_diff / 10.0))

    def _temporal_reason(self, query_year: Optional[int], candidate_year: Optional[int]) -> str:
        """Build temporal reasoning string."""
        if not query_year or not candidate_year:
            return "Year information not available for both cases."
        year_diff = abs(int(query_year) - int(candidate_year))
        return f"Judgment years differ by {year_diff} years."

    def _statutory_reason(self, common_statutes: set) -> str:
        """Build statutory reasoning string."""
        if not common_statutes:
            return "No overlapping statutes or sections detected."
        return f"Common statutes/sections: {', '.join(sorted(common_statutes))}."

    def _short_explanation(
        self,
        common_statutes: set,
        query_case_type: str,
        candidate_case_type: str,
        query_court: str,
        candidate_court: str,
    ) -> str:
        """Build a short similarity explanation."""
        parts = []
        if common_statutes:
            parts.append(f"Both involve {', '.join(sorted(common_statutes))}.")
        if query_case_type and candidate_case_type and query_case_type.lower() == candidate_case_type.lower():
            parts.append(f"Both are {query_case_type} cases.")
        if query_court and candidate_court and query_court == candidate_court:
            parts.append(f"Same court: {query_court}.")
        if not parts:
            parts.append("Similarity based on combined factual and legal signals.")
        return " ".join(parts)

    def _detailed_explanation(self, dimensions: list[SimilarityDimension]) -> str:
        """Build detailed markdown explanation with star ratings."""
        lines = ["### Similarity Breakdown"]
        for dimension in dimensions:
            stars = "*" * int(round(dimension.score * 5))
            lines.append(f"- **{dimension.name}**: {dimension.score:.2f} ({stars}) - {dimension.reason}")
        return "\n".join(lines)
