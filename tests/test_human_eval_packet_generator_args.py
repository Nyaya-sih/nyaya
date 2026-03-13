"""Tests for human eval packet generator script parsing/helpers."""

import importlib.util
import json
from importlib.machinery import ModuleSpec
from pathlib import Path
from typing import cast


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "21_generate_human_eval_packets.py"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_human_eval_packets", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(cast(ModuleSpec, SPEC))
SPEC.loader.exec_module(MODULE)


def test_parse_args_for_human_eval_packets(monkeypatch):
    """Packet generator should parse file/count/mode options."""
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "--source-file",
            "data/evals/in.jsonl",
            "--output-file",
            "data/evals/out.jsonl",
            "--queries",
            "75",
            "--seed",
            "9",
            "--top-k",
            "15",
            "--similarity-mode",
            "fulltext",
        ],
    )
    args = MODULE.parse_args()
    assert args.source_file == "data/evals/in.jsonl"
    assert args.output_file == "data/evals/out.jsonl"
    assert args.queries == 75
    assert args.seed == 9
    assert args.top_k == 15
    assert args.similarity_mode == "fulltext"


def test_load_source_records_filters_query_case_id(tmp_path):
    """Only records with query_case_id should be retained."""
    eval_file = tmp_path / "sample.jsonl"
    rows = [
        {"query_id": "q1", "query_case_id": 11},
        {"query_id": "q2", "query_text": "abc"},
    ]
    eval_file.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    records = MODULE.load_source_records(eval_file)
    assert len(records) == 1
    assert records[0]["query_case_id"] == 11
