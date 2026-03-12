"""Tests for embedding manifest merge behavior."""

import importlib.util
import json
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "13_generate_embeddings.py"
)
SPEC = importlib.util.spec_from_file_location("generate_embeddings", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_write_manifest_merges_existing_entries(tmp_path: Path, monkeypatch):
    """New manifest entries should merge and override by case_id."""
    monkeypatch.chdir(tmp_path)
    out = Path("data/processed/embedding_manifest.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            [
                {"case_id": 1, "status": "indexed"},
                {"case_id": 2, "status": "failed"},
            ]
        ),
        encoding="utf-8",
    )

    MODULE._write_manifest(
        [
            {"case_id": 2, "status": "indexed"},
            {"case_id": 3, "status": "indexed"},
        ]
    )

    merged = json.loads(out.read_text(encoding="utf-8"))
    assert [item["case_id"] for item in merged] == [1, 2, 3]
    assert merged[1]["status"] == "indexed"
