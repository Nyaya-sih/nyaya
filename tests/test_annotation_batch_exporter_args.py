"""Tests for reviewer batch export script."""

import importlib.util
import json
from importlib.machinery import ModuleSpec
from pathlib import Path
from typing import cast


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "24_export_annotation_batch.py"
)
SPEC = importlib.util.spec_from_file_location("export_annotation_batch", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(cast(ModuleSpec, SPEC))
SPEC.loader.exec_module(MODULE)


def test_parse_args_for_batch_export(monkeypatch):
    """Batch exporter should parse reviewer and overlap options."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "--packets-file",
            "data/evals/p.jsonl",
            "--output-dir",
            "data/evals/batches",
            "--reviewers",
            "X,Y",
            "--overlap-percent",
            "15",
            "--seed",
            "7",
        ],
    )
    args = MODULE.parse_args()
    assert args.packets_file == "data/evals/p.jsonl"
    assert args.output_dir == "data/evals/batches"
    assert args.reviewers == "X,Y"
    assert args.overlap_percent == 15
    assert args.seed == 7


def test_split_packets_assigns_overlap_and_round_robin():
    """Split should duplicate overlap packets and distribute remainder."""
    packets = [{"query_id": f"q{i}"} for i in range(10)]
    assignments = MODULE.split_packets(
        packets,
        reviewers=["A", "B"],
        overlap_percent=20,
        seed=42,
    )

    assert set(assignments.keys()) == {"A", "B"}
    # 20% of 10 => 2 overlap records in each reviewer file
    assert len(assignments["A"]) == 6
    assert len(assignments["B"]) == 6


def test_write_batches_creates_files(tmp_path):
    """Writer should create one JSONL file per reviewer."""
    assignments = {
        "A": [{"query_id": "q1"}],
        "B": [{"query_id": "q2"}],
    }
    MODULE.write_batches(tmp_path, assignments)

    a_file = tmp_path / "reviewer_A.jsonl"
    b_file = tmp_path / "reviewer_B.jsonl"
    assert a_file.exists()
    assert b_file.exists()

    a_rows = [
        json.loads(line) for line in a_file.read_text(encoding="utf-8").splitlines()
    ]
    b_rows = [
        json.loads(line) for line in b_file.read_text(encoding="utf-8").splitlines()
    ]
    assert a_rows[0]["query_id"] == "q1"
    assert b_rows[0]["query_id"] == "q2"
