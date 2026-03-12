"""Evaluate retrieval quality on a judged similar-case dataset.

Input (JSONL): data/evals/similar_cases_gold.jsonl

Supported record formats:
1) Offline judged retrieval:
   {
     "query_id": "q1",
     "relevant_case_ids": [101, 102],
     "retrieved_case_ids": [101, 150, 102]
   }

2) Live API by text query:
   {
     "query_id": "q2",
     "relevant_case_ids": [201, 202],
     "query_text": "..."
   }

3) Live API by existing case id:
   {
     "query_id": "q3",
     "relevant_case_ids": [301, 302],
     "query_case_id": 300
   }

Output report: data/processed/retrieval_eval_report.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from src.config.settings import settings


def precision_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    """Compute Precision@k."""
    if k <= 0:
        return 0.0
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for case_id in top_k if case_id in relevant)
    return hits / len(top_k)


def recall_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    """Compute Recall@k."""
    if not relevant or k <= 0:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for case_id in top_k if case_id in relevant)
    return hits / len(relevant)


def mrr_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    """Compute MRR@k."""
    for rank, case_id in enumerate(retrieved[:k], start=1):
        if case_id in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[int], relevant: set[int], k: int) -> float:
    """Compute binary relevance nDCG@k."""
    if k <= 0 or not relevant:
        return 0.0

    dcg = 0.0
    for idx, case_id in enumerate(retrieved[:k], start=1):
        rel = 1.0 if case_id in relevant else 0.0
        if rel > 0:
            dcg += rel / math.log2(idx + 1)

    ideal_hits = min(len(relevant), k)
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(idx + 1) for idx in range(1, ideal_hits + 1))
    if idcg == 0:
        return 0.0
    return dcg / idcg


def load_eval_dataset(path: Path) -> list[dict[str, Any]]:
    """Load JSONL evaluation dataset."""
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def fetch_retrieved_case_ids(record: dict[str, Any], client: httpx.Client) -> list[int]:
    """Resolve retrieved case ids from record (offline or live API)."""
    if "retrieved_case_ids" in record and isinstance(
        record["retrieved_case_ids"], list
    ):
        return [int(case_id) for case_id in record["retrieved_case_ids"]]

    api_host = settings.api_host if settings.api_host != "0.0.0.0" else "localhost"
    base_url = f"http://{api_host}:{settings.api_port}/api/v1/cases"

    if "query_case_id" in record:
        case_id = int(record["query_case_id"])
        response = client.get(f"{base_url}/{case_id}/similar", params={"top_k": 20})
        response.raise_for_status()
        payload = response.json()
        return [int(item["case_id"]) for item in payload.get("results", [])]

    query_text = str(record.get("query_text", "")).strip()
    if len(query_text) < 100:
        return []
    response = client.post(
        f"{base_url}/similar",
        json={"text": query_text, "top_k": 20, "similarity_mode": "combined"},
    )
    response.raise_for_status()
    payload = response.json()
    return [int(item["case_id"]) for item in payload.get("results", [])]


def evaluate(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate retrieval metrics over records."""
    if not records:
        return {
            "queries_evaluated": 0,
            "metrics": {
                "precision_at_10": 0.0,
                "recall_at_20": 0.0,
                "mrr_at_10": 0.0,
                "ndcg_at_10": 0.0,
            },
        }

    rows = []
    with httpx.Client(timeout=120) as client:
        for record in records:
            query_id = str(record.get("query_id", "unknown"))
            relevant = {int(case_id) for case_id in record.get("relevant_case_ids", [])}
            if not relevant:
                continue

            try:
                retrieved = fetch_retrieved_case_ids(record, client)
            except Exception as exc:
                logger.warning(
                    "Failed to resolve retrieved ids", query_id=query_id, error=str(exc)
                )
                continue

            rows.append(
                {
                    "query_id": query_id,
                    "precision_at_10": precision_at_k(retrieved, relevant, 10),
                    "recall_at_20": recall_at_k(retrieved, relevant, 20),
                    "mrr_at_10": mrr_at_k(retrieved, relevant, 10),
                    "ndcg_at_10": ndcg_at_k(retrieved, relevant, 10),
                }
            )

    if not rows:
        return {
            "queries_evaluated": 0,
            "metrics": {
                "precision_at_10": 0.0,
                "recall_at_20": 0.0,
                "mrr_at_10": 0.0,
                "ndcg_at_10": 0.0,
            },
            "query_breakdown": [],
        }

    metric_names = ["precision_at_10", "recall_at_20", "mrr_at_10", "ndcg_at_10"]
    averages = {
        name: sum(float(row[name]) for row in rows) / len(rows) for name in metric_names
    }

    return {
        "queries_evaluated": len(rows),
        "metrics": averages,
        "query_breakdown": rows,
    }


def ensure_template_eval_file(path: Path) -> None:
    """Create a starter template file when eval set is missing."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    template = {
        "query_id": "sample_1",
        "relevant_case_ids": [101, 102],
        "retrieved_case_ids": [101, 200, 102],
    }
    path.write_text(json.dumps(template) + "\n", encoding="utf-8")


def main() -> None:
    """Run retrieval quality evaluation and write report."""
    eval_path = Path("data/evals/similar_cases_gold.jsonl")
    ensure_template_eval_file(eval_path)
    records = load_eval_dataset(eval_path)
    report = evaluate(records)

    output_path = Path("data/processed/retrieval_eval_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info(
        "Retrieval evaluation complete",
        queries=report.get("queries_evaluated", 0),
        precision_at_10=report.get("metrics", {}).get("precision_at_10", 0.0),
        recall_at_20=report.get("metrics", {}).get("recall_at_20", 0.0),
        ndcg_at_10=report.get("metrics", {}).get("ndcg_at_10", 0.0),
        path=str(output_path),
    )


if __name__ == "__main__":
    main()
