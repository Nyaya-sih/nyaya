"""Evaluate Phase 4 courtroom quality on curated prompts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from src.features.courtroom.schemas import CourtroomAnalyzeRequest
from src.features.courtroom.service import CourtroomService


@dataclass
class CourtroomEvalCase:
    name: str
    case_text: str


EVAL_SET = [
    CourtroomEvalCase(
        name="criminal_bail",
        case_text=(
            "Accused seeks bail in a non-bailable offence alleging false implication, "
            "while prosecution cites flight risk and witness intimidation concerns."
        ),
    ),
    CourtroomEvalCase(
        name="constitutional_due_process",
        case_text=(
            "Petitioner challenges administrative detention alleging Article 21 and 22 violations, "
            "with dispute around procedural fairness and proportionality."
        ),
    ),
    CourtroomEvalCase(
        name="economic_offence",
        case_text=(
            "Company officers face fraud allegations under financial statute; defense argues absence "
            "of mens rea and procedural irregularity in seizure and confession recording."
        ),
    ),
]


def main() -> None:
    service = CourtroomService()

    per_run: list[dict] = []
    completed = 0
    degraded = 0

    for mode in ["quick", "full"]:
        for case in EVAL_SET:
            req = CourtroomAnalyzeRequest(
                mode=mode,
                include_rebuttal=(mode == "full"),
                source_type="text",
                case_text=case.case_text,
                top_k_legal=8,
                top_k_cases=0,
            )
            created = service.create_analysis(req)
            report = service.get_analysis(created.analysis_id)

            if report.status in {"completed", "degraded"}:
                completed += 1
            if report.status == "degraded":
                degraded += 1

            per_run.append(
                {
                    "case": case.name,
                    "mode": mode,
                    "analysis_id": report.analysis_id,
                    "status": report.status,
                    "role_count": len(report.role_analyses),
                    "evaluation_count": len(report.evaluation_breakdown),
                    "rebuttal_enabled": report.rebuttal_enabled,
                    "consensus_meter": report.transparency_dashboard.consensus_meter,
                    "disagreement_index": report.transparency_dashboard.disagreement_index,
                    "estimated_cost_usd": report.transparency_dashboard.estimated_cost_usd,
                    "confidence": report.synthesis.confidence,
                    "warnings": report.warnings,
                }
            )

    total = len(per_run)
    avg_consensus = round(
        sum(run["consensus_meter"] for run in per_run) / total if total else 0.0, 3
    )
    avg_confidence = round(
        sum(run["confidence"] for run in per_run) / total if total else 0.0, 3
    )
    avg_cost = round(
        sum(run["estimated_cost_usd"] for run in per_run) / total if total else 0.0,
        4,
    )

    summary = {
        "total_runs": total,
        "completion_rate": round(completed / total if total else 0.0, 3),
        "degraded_rate": round(degraded / total if total else 0.0, 3),
        "avg_consensus_meter": avg_consensus,
        "avg_synthesis_confidence": avg_confidence,
        "avg_estimated_cost_usd": avg_cost,
        "runs": per_run,
    }

    out = Path("data/processed/courtroom_eval_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"WROTE: {out}")


if __name__ == "__main__":
    main()
