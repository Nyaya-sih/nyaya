"""Tests for embedding script CLI argument parsing."""

import importlib.util
from pathlib import Path


def _load_module(script_name: str, module_name: str):
    path = Path(__file__).resolve().parents[1] / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_args_generate_embeddings_yes(monkeypatch):
    """13 script should parse --yes and batch size."""
    module = _load_module("13_generate_embeddings.py", "gen_embeddings")
    monkeypatch.setattr("sys.argv", ["prog", "--yes", "--batch-size", "25"])
    args = module.parse_args()
    assert args.yes is True
    assert args.batch_size == 25


def test_parse_args_generate_fulltext_embeddings_defaults(monkeypatch):
    """14 script should expose default options."""
    module = _load_module("14_generate_fulltext_embeddings.py", "gen_fulltext")
    monkeypatch.setattr("sys.argv", ["prog"])
    args = module.parse_args()
    assert args.yes is False
    assert args.batch_size == 50
