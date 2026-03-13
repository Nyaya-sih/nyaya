"""Tests for human gold builder script parsing and transforms."""

import importlib.util
import json
from importlib.machinery import ModuleSpec
from pathlib import Path
from typing import cast


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "22_build_human_gold_from_packets.py"
)
SPEC = importlib.util.spec_from_file_location("build_human_gold", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(cast(ModuleSpec, SPEC))
SPEC.loader.exec_module(MODULE)


def test_parse_args_for_human_gold_builder(monkeypatch):
    """Builder should parse packet paths and min judgment threshold."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "--packets-file",
            "data/evals/p.jsonl",
            "--output-file",
            "data/evals/gold.jsonl",
            "--min-judgments",
            "5",
        ],
    )
    args = MODULE.parse_args()
    assert args.packets_file == "data/evals/p.jsonl"
    assert args.output_file == "data/evals/gold.jsonl"
    assert args.min_judgments == 5


def test_to_gold_record_filters_unlabeled_candidates():
    """Only labeled candidates should be emitted as judgments."""
    packet = {
        "query_id": "case_1",
        "query_case_id": 1,
        "similarity_mode": "fulltext",
        "candidates": [
            {"case_id": 2, "label": 2, "note": "strong"},
            {"case_id": 3, "label": "1", "note": "partial"},
            {"case_id": 4, "label": None, "note": ""},
        ],
    }

    row = MODULE.to_gold_record(packet, min_judgments=2)
    assert row is not None
    assert row["query_case_id"] == 1
    assert len(row["judgments"]) == 2
    assert row["judgments"][0]["label"] == 2
    assert row["judgments"][1]["label"] == 1


def test_load_packets_reads_jsonl(tmp_path):
    """Packet loader should parse JSONL rows."""
    packet_file = tmp_path / "packets.jsonl"
    rows = [{"query_case_id": 1}, {"query_case_id": 2}]
    packet_file.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    loaded = MODULE.load_packets(packet_file)
    assert len(loaded) == 2
