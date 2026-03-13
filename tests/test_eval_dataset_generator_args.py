"""Tests for eval dataset generator CLI parsing."""

import importlib.util
from importlib.machinery import ModuleSpec
from pathlib import Path
from typing import cast


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "20_generate_eval_dataset.py"
)
SPEC = importlib.util.spec_from_file_location("generate_eval_dataset", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(cast(ModuleSpec, SPEC))
SPEC.loader.exec_module(MODULE)


def test_parse_args_for_eval_dataset_generation(monkeypatch):
    """Generator should parse query count and seed options."""
    monkeypatch.setattr("sys.argv", ["prog", "--queries", "200", "--seed", "7"])
    args = MODULE.parse_args()
    assert args.queries == 200
    assert args.seed == 7


def test_normalize_sections_handles_list_and_string():
    """Section normalization should uppercase and trim tokens."""
    assert MODULE._normalize_sections([" section 302 ", "CrPC 164"]) == [
        "SECTION 302",
        "CRPC 164",
    ]
    assert MODULE._normalize_sections(" ipc 304 ") == ["IPC 304"]
