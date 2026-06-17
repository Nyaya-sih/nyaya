"""Answer generation scaffold for legal assistant."""

from loguru import logger

from src.config.settings import settings
from src.features.legal_assistant.retriever import EvidenceChunk
from src.utils.llm_client import LLMClient


class AnswerGenerator:
    """Deterministic answer generator for iteration 0/1.

    Iteration 4 will integrate model-backed generation with strict citation grounding.
    """

    def generate(
        self,
        question: str,
        built_context: str,
        has_context: bool,
        evidence: list[EvidenceChunk],
    ) -> str:
        """Generate answer text constrained to retrieved evidence."""
        if not evidence:
            return (
                "I am unsure based on the currently available evidence. Please provide more "
                "specific facts, statute references, or case context so I can respond with "
                "stronger citation support."
            )

        top = evidence[:5]

        if self.llm_client is not None:
            citation_ids = [item.citation_id for item in top if item.citation_id]
            system_prompt = (
                "You are NyayaAI legal research assistant. "
                "Answer only from supplied evidence. "
                "Do not invent statutes, sections, or facts. "
                "If support is weak, say you are unsure. "
                "Use professional Indian legal drafting style suitable for a judicial brief. "
                "Prefer references in the form 'Section X of <Act Name>' or 'Article X of the Constitution'. "
                "For every substantive proposition, append supporting citation ids in brackets using only the provided ids. "
                "Use only numeric citation labels like [CIT-1], [CIT-2]. "
                "Never output placeholders such as [chunk_id], [CIT], or [citation]."
            )
            evidence_lines = []
            for item in top:
                evidence_lines.append(
                    f"{item.citation_id} | {item.act_or_case} | {item.section_or_article or 'n/a'} | score={item.score:.2f}\n"
                    f"{item.excerpt[:500]}"
                )

            prompt = (
                f"Question:\n{question}\n\n"
                f"Has active case context: {'yes' if has_context else 'no'}\n\n"
                "Evidence:\n" + "\n\n".join(evidence_lines) + "\n\n"
                f"Allowed citation ids: {', '.join(citation_ids)}\n\n"
                "Return a concise, formal answer using this structure exactly:\n"
                "1) Governing Provisions: identify applicable sections/articles with Act names.\n"
                "2) Legal Test / Conditions: list the operative statutory conditions in numbered points.\n"
                "3) Application Note: brief professional caveat on judicial discretion or fact sensitivity.\n"
                "Avoid conversational phrasing like 'what this means'. "
                "Do not include markdown headings."
            )
            try:
                response = self.llm_client.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.2,
                    max_tokens=500,
                )
                if response and response.strip():
                    cleaned = response.replace("[chunk_id]", "")
                    cleaned = cleaned.replace("[CIT]", "").replace("[citation]", "")
                    return cleaned.strip()
            except Exception as exc:
                logger.warning(
                    "Assistant LLM generation failed; using deterministic fallback",
                    error=str(exc),
                )

        lead = (
            "Based on retrieved legal material, the strongest support points to: "
            if has_context
            else "Based on retrieved legal material (without active case context), the strongest support points to: "
        )
        bullets = []
        for item in top:
            section = item.section_or_article or "Relevant provision"
            bullets.append(
                f"{item.act_or_case} - {section}: {item.excerpt[:220].strip()}"
            )

        joined = "\n".join(f"- {b}" for b in bullets)
        return (
            f"{lead}\n"
            f"{joined}\n"
            "These points should be verified against the full text of the cited provisions "
            "and recent binding precedents before acting on them."
        )

    def __init__(self) -> None:
        self.llm_client = None
        if settings.has_llm_key():
            try:
                # Keep model aligned with existing lightweight query-metadata model.
                self.llm_client = LLMClient(model=settings.query_metadata_model)
            except Exception as exc:
                logger.warning(
                    "Assistant LLM layer unavailable; using deterministic fallback",
                    error=str(exc),
                )
