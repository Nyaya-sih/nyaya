"""Benchmark Phase 5 outcome tendency classifiers on stored case data."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import settings
from src.database.models import Case
from src.features.outcome_tendency.feature_builder import OutcomeFeatureBuilder
from src.features.outcome_tendency.model_runner import OutcomeModelRunner


def main() -> None:
    engine = create_engine(settings.database_url, echo=False)
    session_local = sessionmaker(bind=engine)

    builder = OutcomeFeatureBuilder()
    runner = OutcomeModelRunner()

    with session_local() as session:
        cases = (
            session.query(Case)
            .filter(Case.verdict.isnot(None))
            .filter(Case.validation_status != "invalid")
            .all()
        )

    dataset = builder.build(cases)
    benchmark = runner.benchmark(dataset.rows, dataset.targets)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_cases_scanned": len(cases),
        "total_labeled_rows": len(dataset.rows),
        "benchmark": benchmark,
    }

    out = Path("data/processed/tendency_benchmark_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"WROTE: {out}")


if __name__ == "__main__":
    main()
