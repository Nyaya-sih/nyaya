"""Tests for human annotation validator script."""

import importlib.util
import json
from importlib.machinery import ModuleSpec
from pathlib import Path
from typing import cast


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "23_validate_human_annotations.py"
)
SPEC = importlib.util.spec_from_file_location("validate_human_annotations", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(cast(ModuleSpec, SPEC))
SPEC.loader.exec_module(MODULE)


def test_parse_args_for_annotation_validator(monkeypatch):
    """Validator should parse packet path and minimum labels."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "--packets-file",
            "data/evals/p.jsonl",
            "--output-file",
            "data/processed/r.json",
            "--min-labeled-per-query",
            "4",
        ],
    )
    args = MODULE.parse_args()
    assert args.packets_file == "data/evals/p.jsonl"
    assert args.output_file == "data/processed/r.json"
    assert args.min_labeled_per_query == 4


def test_validate_packets_reports_completion_and_distribution():
    """Validation should compute query completion and label distribution."""
    packets = [
        {
            "query_id": "q1",
            "candidates": [
                {"case_id": 1, "label": 2},
                {"case_id": 2, "label": 1},
                {"case_id": 3, "label": 0},
            ],
        },
        {
            "query_id": "q2",
            "candidates": [
                {"case_id": 4, "label": 1},
                {"case_id": 5, "label": None},
            ],
        },
    ]

    report = MODULE.validate_packets(packets, min_labeled_per_query=2)
    assert report["summary"]["total_queries"] == 2
    assert report["summary"]["queries_with_any_labels"] == 2
    assert report["summary"]["queries_meeting_min_labels"] == 1
    assert report["label_distribution"] == {"0": 1, "1": 2, "2": 1}
    assert report["status"] == "warn"


def test_load_packets_reads_jsonl(tmp_path):
    """Packet loader should read JSONL rows."""
    packet_file = tmp_path / "packets.jsonl"
    rows = [{"query_id": "q1"}, {"query_id": "q2"}]
    packet_file.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    loaded = MODULE.load_packets(packet_file)
    assert len(loaded) == 2
