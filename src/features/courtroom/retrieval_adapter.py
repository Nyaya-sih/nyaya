"""Role-aware retrieval adapter for courtroom analyses."""

from __future__ import annotations

import os
from typing import Any

from src.features.legal_assistant.query_parser import QueryParser
from src.features.legal_assistant.retriever import AssistantRetriever, EvidenceChunk


class CourtroomRetrievalAdapter:
    """Fetch role-aware legal evidence from Phase 3 retrieval stack."""

    ROLE_QUERY_SUFFIX = {
        "Prosecution Counsel": (
            "Focus on prosecutorial burden, statutory ingredients, and evidentiary thresholds."
        ),
        "Defense Counsel": (
            "Focus on defense rights, procedural safeguards, burden of proof gaps, and reasonable doubt."
        ),
        "Constitutional Expert": (
            "Focus on constitutional rights, proportionality, due process, and statutory validity."
        ),
        "Legal Analyst": (
            "Focus on neutral statutory interpretation, procedural regularity, and evidentiary coherence."
        ),
    }

    def __init__(self) -> None:
        self.query_parser = QueryParser()
        self.retriever = AssistantRetriever()
        self.enabled = not bool(os.getenv("PYTEST_CURRENT_TEST"))

    def retrieve_for_role(
        self,
        *,
        role_name: str,
        case_text: str,
        top_k_legal: int,
    ) -> tuple[list[dict[str, str]], list[str]]:
        """Return compact role-aware evidence blocks and warnings."""
        warnings: list[str] = []
        if not self.enabled:
            warnings.append("Retrieval adapter disabled in test runtime.")
            return [], warnings

        base_query = case_text.strip()[:1400]
        if not base_query:
            return [], warnings

        suffix = self.ROLE_QUERY_SUFFIX.get(
            role_name, "Focus on applicable legal provisions."
        )
        role_query = f"{base_query}\n\n{suffix}"

        parsed = self.query_parser.parse(role_query)
        chunks: list[EvidenceChunk] = self.retriever.retrieve(
            question=role_query,
            context_text="",
            top_k=max(3, top_k_legal),
            statutes_hint=parsed.statutes_hint,
            sections_hint=parsed.sections_hint,
        )

        blocks: list[dict[str, str]] = []
        seen: set[str] = set()
        for chunk in chunks:
            if not chunk.citation_id or chunk.citation_id in seen:
                continue
            seen.add(chunk.citation_id)
            blocks.append(
                {
                    "citation_id": chunk.citation_id,
                    "source": chunk.act_or_case,
                    "section": chunk.section_or_article or "n/a",
                    "excerpt": chunk.excerpt,
                    "score": f"{chunk.score:.3f}",
                }
            )
            if len(blocks) >= top_k_legal:
                break

        if not blocks:
            warnings.append(f"No legal KB evidence retrieved for role '{role_name}'.")

        return blocks, warnings
