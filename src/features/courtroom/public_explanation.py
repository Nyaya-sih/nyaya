"""Public explanation contract and fail-closed source quotation validation."""

from pydantic import ValidationError

from src.features.courtroom.schemas import PublicExplanation


PUBLIC_EXPLANATION_RULES = (
    "Require public_explanation with concise public reasons, not private chain-of-thought. "
    "Distinguish supplied facts from assumptions. Include the strongest counterargument and "
    "uncertainties; use empty arrays only when none apply. Explain the changed or retained "
    "position in change_summary (initial position for the first round). "
    "Quote only supplied case material (source_ref='case_text') or supplied evidence citation_id. "
    "Include supporting source quotations for an approvable conclusion; an empty evidence list "
    "means the conclusion is not source-grounded. Textual PDF page markers are navigation aids, "
    "not authenticated source identifiers. "
    "Never invent page numbers, source identifiers, citations or quotations. "
    "quote_verified is computed by the server; quotation matching is not factual or legal validation. "
    "Confidence is an uncalibrated model self-assessment, not a validated probability."
)

PUBLIC_EXPLANATION_SCHEMA = {
    "conclusion_basis": "concise basis for the conclusion",
    "supporting_evidence": [
        {"source_ref": "case_text or supplied citation_id", "quote": "verbatim quotation",
         "relevance": "why this supports the conclusion", "quote_verified": False}
    ],
    "assumptions": ["assumption, distinguished from supplied facts"],
    "counterarguments": ["strongest competing argument"],
    "uncertainty": ["missing facts or legal uncertainty"],
    "change_summary": "changed or retained position and public reasons why",
}


def validate_public_explanation(
    value: object, case_text: str, evidence_blocks: list[dict[str, str]] | None = None,
) -> tuple[PublicExplanation | None, list[str]]:
    """Match quotations only to their actual supplied source, ignoring model booleans."""
    if not isinstance(value, dict):
        return None, ["Public explanation missing; supporting reasons were not supplied."]
    try:
        explanation = PublicExplanation.model_validate(value)
    except ValidationError:
        return None, ["Public explanation invalid; structured supporting reasons unavailable."]
    if not explanation.conclusion_basis.strip():
        return None, ["Public explanation invalid; conclusion basis missing."]

    sources = {"case_text": [" ".join(case_text.split())]}
    for block in evidence_blocks or []:
        source_ref = block.get("citation_id", "").strip()
        if source_ref and source_ref != "case_text":
            sources.setdefault(source_ref, []).append(" ".join(block.get("excerpt", "")[:500].split()))
    warnings = []
    for evidence in explanation.supporting_evidence:
        quote = " ".join(evidence.quote.split())
        source_ref = evidence.source_ref.strip()
        evidence.quote_verified = (
            len(quote) >= 12 and any(quote in text for text in sources.get(source_ref, []))
        )
        if evidence.quote_verified:
            evidence.source_ref = source_ref
        else:
            # An unverified model citation must not look like a canonical source anchor.
            evidence.source_ref = "unverified"
            warnings.append("Public evidence quotation or source could not be verified.")
    return explanation, warnings
