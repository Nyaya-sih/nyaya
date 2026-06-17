"""Evaluate Phase 5 outcome tendency quality on curated scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import settings
from src.features.outcome_tendency.schemas import OutcomeTendencyRequest
from src.features.outcome_tendency.service import OutcomeTendencyService


@dataclass
class TendencyEvalCase:
    name: str
    source_type: str
    case_text: str | None = None
    case_id: int | None = None


EVAL_SET = [
    TendencyEvalCase(
        name="criminal_bail_text",
        source_type="text",
        case_text=(
            "Accused seeks bail while prosecution cites witness intimidation and flight risk "
            "in a criminal matter with multiple charges and procedural objections."
        ),
    ),
    TendencyEvalCase(
        name="constitutional_due_process_text",
        source_type="text",
        case_text=(
            "Constitutional petition alleges arbitrary state action under Articles 14 and 21, "
            "raising procedural fairness and proportionality concerns."
        ),
    ),
    TendencyEvalCase(
        name="economic_offence_text",
        source_type="text",
        case_text=(
            "Economic offence case involving alleged fraud and financial misreporting where "
            "defense disputes mens rea and evidentiary integrity."
        ),
    ),
    TendencyEvalCase(name="case_id_probe", source_type="case_id", case_id=42),
]


def main() -> None:
    service = OutcomeTendencyService()
    engine = create_engine(settings.database_url, echo=False)
    session_local = sessionmaker(bind=engine)

    run_rows: list[dict] = []

    with session_local() as db_session:
        for case in EVAL_SET:
            payload = OutcomeTendencyRequest(
                mode="baseline",
                source_type=case.source_type,  # type: ignore[arg-type]
                case_text=case.case_text,
                case_id=case.case_id,
                top_k_similar=300,
            )
            response = service.analyze(payload, db_session=db_session)

            run_rows.append(
                {
                    "case": case.name,
                    "analysis_id": response.analysis_id,
                    "status": response.status,
                    "sample_size": response.sample_size,
                    "dominant_outcome": (
                        max(
                            response.outcome_distribution,
                            key=lambda item: item.percentage,
                        ).label
                        if response.outcome_distribution
                        else None
                    ),
                    "confidence_level": response.confidence_band.level,
                    "confidence_reliability": response.confidence_band.reliability_score,
                    "warning_count": len(response.warnings),
                    "disparity_flag": response.bias_audit.disparity_flag,
                    "drift_flag": response.bias_audit.drift_flag,
                }
            )

    total = len(run_rows)
    completed = sum(1 for item in run_rows if item["status"] == "completed")
    insufficient = sum(1 for item in run_rows if item["status"] == "insufficient_data")
    avg_sample_size = round(
        sum(item["sample_size"] for item in run_rows) / total if total else 0.0, 1
    )
    avg_reliability = round(
        sum(item["confidence_reliability"] for item in run_rows) / total
        if total
        else 0.0,
        3,
    )
    warning_rate = round(
        sum(1 for item in run_rows if item["warning_count"] > 0) / total
        if total
        else 0.0,
        3,
    )
    disparity_flag_rate = round(
        sum(1 for item in run_rows if item["disparity_flag"]) / total if total else 0.0,
        3,
    )
    drift_flag_rate = round(
        sum(1 for item in run_rows if item["drift_flag"]) / total if total else 0.0,
        3,
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_runs": total,
        "completion_rate": round(completed / total if total else 0.0, 3),
        "insufficient_data_rate": round(insufficient / total if total else 0.0, 3),
        "avg_sample_size": avg_sample_size,
        "avg_confidence_reliability": avg_reliability,
        "warning_rate": warning_rate,
        "disparity_flag_rate": disparity_flag_rate,
        "drift_flag_rate": drift_flag_rate,
        "runs": run_rows,
    }

    out = Path("data/processed/tendency_eval_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"WROTE: {out}")


if __name__ == "__main__":
    main()
