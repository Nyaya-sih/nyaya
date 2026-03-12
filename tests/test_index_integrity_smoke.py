"""Smoke tests for index integrity checker helpers."""

import importlib.util
import json
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "16_verify_index_integrity.py"
)
SPEC = importlib.util.spec_from_file_location("verify_index_integrity", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_load_manifest_stats_counts_indexed_and_failed(tmp_path: Path):
    """Manifest parser should count indexed/failed entries correctly."""
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {"case_id": 1, "status": "indexed"},
                {"case_id": 2, "status": "failed"},
                {"case_id": 1, "status": "indexed"},
            ]
        ),
        encoding="utf-8",
    )

    stats = MODULE.load_manifest_stats(manifest_path)
    assert stats["total_entries"] == 3
    assert stats["indexed_entries"] == 2
    assert stats["failed_entries"] == 1
    assert stats["unique_case_ids"] == 2


def test_compute_integrity_checks_pass_state():
    """Checks should pass when counts are aligned."""
    report = MODULE.compute_integrity_checks(
        db_non_invalid=100,
        qdrant_counts={"combined": 100, "factual": 100, "legal": 100, "fulltext": 100},
        manifest_stats={"indexed_entries": 100},
        tolerance=0,
    )
    assert report["status"] == "pass"
    assert report["checks"]["combined_matches_db_non_invalid"]["pass"] is True


def test_compute_integrity_checks_warn_state():
    """Checks should warn when major drifts are present."""
    report = MODULE.compute_integrity_checks(
        db_non_invalid=100,
        qdrant_counts={"combined": 80, "factual": 100, "legal": 100, "fulltext": 95},
        manifest_stats={"indexed_entries": 70},
        tolerance=0,
    )
    assert report["status"] == "warn"
    assert report["checks"]["combined_matches_db_non_invalid"]["pass"] is False
