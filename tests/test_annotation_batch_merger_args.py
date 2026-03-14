"""Tests for annotation batch merge script."""

import importlib.util
import json
from importlib.machinery import ModuleSpec
from pathlib import Path
from typing import cast


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "25_merge_annotator_batches.py"
)
SPEC = importlib.util.spec_from_file_location("merge_annotator_batches", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(cast(ModuleSpec, SPEC))
SPEC.loader.exec_module(MODULE)


def test_parse_args_for_batch_merger(monkeypatch):
    """Batch merger should parse paths and file pattern."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "--batches-dir",
            "data/evals/human_batches",
            "--pattern",
            "reviewer_*.jsonl",
            "--output-file",
            "data/evals/merged.jsonl",
            "--conflict-report",
            "data/processed/conflicts.json",
        ],
    )
    args = MODULE.parse_args()
    assert args.batches_dir == "data/evals/human_batches"
    assert args.pattern == "reviewer_*.jsonl"
    assert args.output_file == "data/evals/merged.jsonl"
    assert args.conflict_report == "data/processed/conflicts.json"


def test_merge_batches_detects_tie_conflicts():
    """Tie labels across reviewers should be emitted as conflicts."""
    packet_a = {
        "query_id": "q1",
        "query_case_id": 101,
        "candidates": [{"case_id": 5001, "label": 2, "note": "strong"}],
    }
    packet_b = {
        "query_id": "q1",
        "query_case_id": 101,
        "candidates": [{"case_id": 5001, "label": 1, "note": "partial"}],
    }
    merged, report = MODULE.merge_batches({"A": [packet_a], "B": [packet_b]})

    assert len(merged) == 1
    assert merged[0]["candidates"][0]["label"] is None
    assert report["summary"]["conflicts"] == 1


def test_load_reviewer_batches_reads_files(tmp_path):
    """Loader should parse reviewer_*.jsonl files."""
    a_file = tmp_path / "reviewer_A.jsonl"
    b_file = tmp_path / "reviewer_B.jsonl"
    a_file.write_text(json.dumps({"query_id": "q1", "query_case_id": 1}) + "\n")
    b_file.write_text(json.dumps({"query_id": "q2", "query_case_id": 2}) + "\n")

    batches = MODULE.load_reviewer_batches(tmp_path, "reviewer_*.jsonl")
    assert set(batches.keys()) == {"A", "B"}
    assert batches["A"][0]["query_id"] == "q1"
