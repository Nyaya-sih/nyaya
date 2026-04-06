"""Smoke tests for legal KB integrity script helpers."""

import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "32_verify_legal_kb_integrity.py"
)
SPEC = importlib.util.spec_from_file_location("verify_legal_kb_integrity", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_evaluate_metadata_reports_full_coverage():
    """Metadata coverage should be 1.0 for fully populated chunk rows."""
    rows = [
        {
            "chunk_id": "a",
            "source_id": "s",
            "source_type": "statute",
            "act_name": "Act",
            "section_or_article": "Section 1",
            "text": "Body",
            "source_version_hash": "h",
        }
    ]
    metadata = MODULE.evaluate_metadata(rows)
    assert metadata["total_chunks"] == 1
    assert metadata["coverage"]["chunk_id"] == 1.0


def test_compute_checks_warn_on_count_mismatch():
    """Integrity status should warn when qdrant count mismatches manifest."""
    metadata = {
        "coverage": {
            "chunk_id": 1.0,
            "source_id": 1.0,
            "source_type": 1.0,
            "act_name": 1.0,
            "section_or_article": 1.0,
            "text": 1.0,
            "source_version_hash": 1.0,
        }
    }
    integrity = MODULE.compute_checks(
        chunks_count=100,
        indexed_count=100,
        failed_count=0,
        qdrant_count=95,
        metadata=metadata,
    )
    assert integrity["status"] == "warn"
    assert integrity["checks"]["qdrant_matches_indexed_manifest"]["pass"] is False
