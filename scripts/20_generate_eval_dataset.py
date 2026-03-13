"""Generate a larger retrieval eval dataset from existing case metadata.

This creates heuristic relevance labels for Phase 2 benchmarking:
- Query case: sampled non-invalid cases
- Relevant cases: same court + case_type + verdict (fallbacks applied)

Output: data/evals/similar_cases_gold.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import settings
from src.database.models import Case


def parse_args() -> argparse.Namespace:
    """Parse CLI args for eval dataset generation."""
    parser = argparse.ArgumentParser(
        description="Generate heuristic retrieval eval dataset"
    )
    parser.add_argument(
        "--queries", type=int, default=250, help="Number of query records to generate"
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--max-relevant",
        type=int,
        default=5,
        help="Maximum relevant case IDs per query",
    )
    return parser.parse_args()


def main() -> None:
    """Generate and persist eval dataset records."""
    args = parse_args()
    random.seed(args.seed)

    engine = create_engine(settings.database_url, echo=False)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    try:
        rows = (
            session.query(
                Case.id,
                Case.court,
                Case.case_type,
                Case.verdict,
                Case.date_of_judgment,
                Case.sections_invoked,
            )
            .filter(Case.validation_status != "invalid")
            .all()
        )
    finally:
        session.close()

    cases = []
    for row in rows:
        case_id = int(row[0])
        court = str(row[1] or "")
        case_type = str(row[2] or "")
        verdict = str(row[3] or "")
        year = row[4].year if row[4] else 0
        sections = _normalize_sections(row[5])
        cases.append(
            {
                "id": case_id,
                "court": court,
                "case_type": case_type,
                "verdict": verdict,
                "year": int(year),
                "sections": sections,
            }
        )

    by_strict: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for case in cases:
        by_strict[(case["court"], case["case_type"], case["verdict"])].append(case)

    candidates = [case for case in cases if case["case_type"]]
    random.shuffle(candidates)

    records = []
    for case in candidates:
        if not case["sections"]:
            continue

        strict_pool = [
            item
            for item in by_strict[(case["court"], case["case_type"], case["verdict"])]
            if item["id"] != case["id"]
        ]
        if not strict_pool:
            continue

        overlap_pool = []
        query_sections = set(case["sections"])
        for item in strict_pool:
            overlap_count = len(query_sections & set(item["sections"]))
            if overlap_count > 0:
                overlap_pool.append((item, overlap_count))

        if not overlap_pool:
            continue

        ranked = sorted(
            overlap_pool,
            key=lambda pair: (
                -pair[1],
                abs((pair[0]["year"] or 0) - (case["year"] or 0)),
            ),
        )
        relevant_ids = [item["id"] for item, _ in ranked[: max(1, args.max_relevant)]]
        if not relevant_ids:
            continue

        records.append(
            {
                "query_id": f"case_{case['id']}",
                "query_case_id": case["id"],
                "similarity_mode": "fulltext",
                "relevant_case_ids": relevant_ids,
            }
        )
        if len(records) >= args.queries:
            break

    output = Path("data/evals/similar_cases_gold.jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record) + "\n")

    logger.info("Eval dataset generated", records=len(records), path=str(output))


def _normalize_sections(value: Any) -> list[str]:
    """Normalize section values for overlap matching."""
    if value is None:
        return []
    if isinstance(value, list):
        raw = value
    else:
        raw = [value]

    normalized = []
    for item in raw:
        if not item:
            continue
        token = " ".join(str(item).strip().split()).upper()
        if token:
            normalized.append(token)
    return normalized


if __name__ == "__main__":
    main()
