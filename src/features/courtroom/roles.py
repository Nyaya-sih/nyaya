"""Role definitions and prompt packs for simulated courtroom."""

from __future__ import annotations

from typing import Literal


RoleName = Literal[
    "Prosecution Counsel",
    "Defense Counsel",
    "Constitutional Expert",
    "Legal Analyst",
    "Presiding Judge",
]


QUICK_MODE_ROLES: list[RoleName] = [
    "Prosecution Counsel",
    "Defense Counsel",
    "Legal Analyst",
]

FULL_MODE_ROLES: list[RoleName] = [
    "Prosecution Counsel",
    "Defense Counsel",
    "Constitutional Expert",
    "Legal Analyst",
]


ROLE_MANDATES: dict[RoleName, str] = {
    "Prosecution Counsel": (
        "Build the strongest prosecution/petitioner legal theory. "
        "Focus on statutory elements, evidentiary support, and enforceable relief."
    ),
    "Defense Counsel": (
        "Build the strongest defense/respondent legal theory. "
        "Focus on burden of proof gaps, procedural defects, and alternative interpretations."
    ),
    "Constitutional Expert": (
        "Analyze constitutional rights, validity, proportionality, and due process implications."
    ),
    "Legal Analyst": (
        "Provide a neutral legal analysis balancing merits, procedure, and evidentiary strength."
    ),
    "Presiding Judge": (
        "Synthesize all arguments and produce a reasoned recommendation with unresolved issues."
    ),
}


def build_role_system_prompt(role: RoleName) -> str:
    """Build system prompt for a given courtroom role."""
    mandate = ROLE_MANDATES[role]
    return (
        "You are NyayaAI simulated courtroom legal role engine. "
        "You must operate as the assigned role and remain legally precise. "
        "Do not fabricate sections/cases/facts. "
        "If support is weak, state uncertainty explicitly. "
        f"Role mandate: {mandate}"
    )


def build_role_user_prompt(
    role: RoleName,
    case_text: str,
    mode: str,
    evidence_blocks: list[dict[str, str]] | None = None,
) -> str:
    """Build role-specific user prompt with strict JSON output requirement."""
    evidence_lines = []
    for idx, item in enumerate(evidence_blocks or [], start=1):
        evidence_lines.append(
            f"[{idx}] {item.get('citation_id', '')} | {item.get('source', '')} | "
            f"{item.get('section', 'n/a')} | score={item.get('score', '0.0')}\n"
            f"{item.get('excerpt', '')[:500]}"
        )

    evidence_text = "\n\n".join(evidence_lines)
    return (
        f"Role: {role}\n"
        f"Mode: {mode}\n\n"
        "Case Material:\n"
        f"{case_text[:25000]}\n\n"
        "Retrieved Legal Evidence (cite where relevant):\n"
        f"{evidence_text if evidence_text else 'No retrieval evidence available.'}\n\n"
        "Output rules:\n"
        "1) Return valid JSON only (no markdown fences).\n"
        "2) JSON schema:\n"
        "{\n"
        '  "analysis_text": "<professional legal analysis in 2-5 paragraphs>",\n'
        '  "citations": ["Section ...", "Article ..."],\n'
        '  "confidence": <float 0 to 1>\n'
        "}\n"
        "3) analysis_text must reflect only case facts and generally known Indian legal framing.\n"
        "4) Keep tone professional and law-office/judicial-brief style."
    )
