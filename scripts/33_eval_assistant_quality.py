"""Evaluate assistant quality on curated legal prompts.

Generates simple metrics:
- citation_presence_rate
- high_confidence_rate
- retrieval_mode_distribution
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from src.features.legal_assistant.service import LegalAssistantService


@dataclass
class EvalCase:
    question: str
    expected_hint: str


EVAL_SET = [
    EvalCase("What is punishment for murder under IPC?", "Indian Penal Code"),
    EvalCase("What does Article 14 guarantee?", "Constitution"),
    EvalCase("What are bail safeguards under BNSS?", "Bharatiya Nagarik Suraksha"),
    EvalCase("How do I file a consumer complaint?", "Consumer Protection"),
    EvalCase("What is the scope of Section 302?", "Section 302"),
]


def main() -> None:
    service = LegalAssistantService()
    session = service.create_session()

    results = []
    citation_hits = 0
    high_conf = 0
    mode_counts: dict[str, int] = {}

    for item in EVAL_SET:
        response = service.query(
            session_id=session.session_id,
            question=item.question,
            top_k=8,
            include_history=True,
        )
        cites = response.citations
        has_citation = bool(cites)
        if has_citation:
            citation_hits += 1
        if response.confidence.overall >= 0.6:
            high_conf += 1
        mode_counts[response.retrieval_mode] = (
            mode_counts.get(response.retrieval_mode, 0) + 1
        )

        hint_present = any(
            item.expected_hint.lower()
            in (c.act_or_case + " " + (c.section_or_article or "")).lower()
            for c in cites
        )

        results.append(
            {
                "question": item.question,
                "expected_hint": item.expected_hint,
                "retrieval_mode": response.retrieval_mode,
                "citation_count": len(cites),
                "confidence": response.confidence.overall,
                "hint_present": hint_present,
            }
        )

    summary = {
        "total_questions": len(EVAL_SET),
        "citation_presence_rate": round(citation_hits / len(EVAL_SET), 3),
        "high_confidence_rate": round(high_conf / len(EVAL_SET), 3),
        "retrieval_mode_distribution": mode_counts,
        "results": results,
    }

    out = Path("data/processed/assistant_eval_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"WROTE: {out}")


if __name__ == "__main__":
    main()
