"""Tests for retrieval evaluation metrics helpers."""

import importlib.util
from importlib.machinery import ModuleSpec
from pathlib import Path
from typing import cast


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "17_eval_retrieval_quality.py"
)
SPEC = importlib.util.spec_from_file_location("eval_retrieval_quality", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(cast(ModuleSpec, SPEC))
SPEC.loader.exec_module(MODULE)


def test_precision_recall_mrr_ndcg_values():
    """Metric helpers should compute expected values."""
    retrieved = [1, 4, 2, 8, 9]
    relevant = {1, 2, 3}

    assert MODULE.precision_at_k(retrieved, relevant, 3) == 2 / 3
    assert MODULE.recall_at_k(retrieved, relevant, 5) == 2 / 3
    assert MODULE.mrr_at_k(retrieved, relevant, 10) == 1.0

    ndcg = MODULE.ndcg_at_k(retrieved, relevant, 3)
    assert 0.0 <= ndcg <= 1.0


def test_evaluate_uses_offline_retrieved_case_ids_only():
    """Evaluate should work without API when retrieved_case_ids are provided."""
    records = [
        {
            "query_id": "q1",
            "relevant_case_ids": [1, 2],
            "retrieved_case_ids": [1, 9, 2],
        },
        {
            "query_id": "q2",
            "relevant_case_ids": [10],
            "retrieved_case_ids": [7, 10],
        },
    ]

    report = MODULE.evaluate(records)
    assert report["queries_evaluated"] == 2
    assert report["metrics"]["precision_at_10"] > 0.0
    assert report["metrics"]["recall_at_20"] > 0.0


def test_parse_args_with_max_queries(monkeypatch):
    """Evaluation CLI should parse max query limit."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "--max-queries",
            "25",
            "--eval-file",
            "data/evals/custom.jsonl",
            "--output-file",
            "data/processed/custom_report.json",
        ],
    )
    args = MODULE.parse_args()
    assert args.max_queries == 25
    assert args.eval_file == "data/evals/custom.jsonl"
    assert args.output_file == "data/processed/custom_report.json"


def test_extract_relevance_supports_human_judgments():
    """Human judgment labels should map to binary+graded relevance."""
    record = {
        "query_id": "h1",
        "judgments": [
            {"case_id": 101, "label": 2},
            {"case_id": 102, "label": 1},
            {"case_id": 103, "label": 0},
        ],
    }
    binary, graded = MODULE.extract_relevance(record)
    assert binary == {101, 102}
    assert graded == {101: 2, 102: 1, 103: 0}
