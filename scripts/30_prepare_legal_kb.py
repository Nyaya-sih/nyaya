"""Prepare legal knowledge-base chunks from raw legal sources.

Input manifest (JSON): data/raw/legal_kb/sources_manifest.json
Output chunks (JSONL): data/processed/legal_kb_chunks.jsonl
Output report (JSON): data/processed/legal_kb_prepare_report.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from loguru import logger

from src.features.legal_assistant.legal_kb import (
    build_chunks,
    load_sources_manifest,
    read_legal_text,
    validate_chunk_metadata,
    write_manifest_template,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line args for KB preparation."""
    parser = argparse.ArgumentParser(description="Prepare legal KB chunks")
    parser.add_argument(
        "--manifest",
        type=str,
        default="data/raw/legal_kb/sources_manifest.json",
        help="Path to legal source manifest JSON",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/processed/legal_kb_chunks.jsonl",
        help="Output JSONL path for prepared chunks",
    )
    parser.add_argument(
        "--report",
        type=str,
        default="data/processed/legal_kb_prepare_report.json",
        help="Output JSON report path",
    )
    return parser.parse_args()


def main() -> None:
    """Run KB chunk preparation from source manifest."""
    args = parse_args()
    manifest_path = Path(args.manifest)
    output_path = Path(args.output)
    report_path = Path(args.report)

    if not manifest_path.exists():
        write_manifest_template(manifest_path)
        logger.warning(
            "Manifest missing; wrote starter template",
            path=str(manifest_path),
        )

    sources = load_sources_manifest(manifest_path)
    if not sources:
        logger.error("No valid sources found in manifest", path=str(manifest_path))
        report = {
            "status": "error",
            "message": "No valid sources found in manifest",
            "manifest": str(manifest_path),
            "source_count": 0,
            "chunk_count": 0,
            "errors": [],
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return

    prepared_chunks = []
    source_reports = []
    errors: list[str] = []

    for source in sources:
        source_path = Path(source.path)
        if not source_path.exists():
            err = f"Missing source file for {source.source_id}: {source_path}"
            logger.warning(err)
            errors.append(err)
            source_reports.append(
                {
                    "source_id": source.source_id,
                    "status": "missing",
                    "path": str(source_path),
                    "chunks": 0,
                }
            )
            continue

        text = read_legal_text(source_path)
        if not text.strip():
            err = f"Empty extracted text for {source.source_id}: {source_path}"
            logger.warning(err)
            errors.append(err)
            source_reports.append(
                {
                    "source_id": source.source_id,
                    "status": "empty",
                    "path": str(source_path),
                    "chunks": 0,
                }
            )
            continue

        chunks = build_chunks(source, text)
        validation_errors = validate_chunk_metadata(chunks)
        if validation_errors:
            errors.extend(validation_errors)

        prepared_chunks.extend(chunks)
        source_reports.append(
            {
                "source_id": source.source_id,
                "status": "prepared",
                "path": str(source_path),
                "chunks": len(chunks),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for chunk in prepared_chunks:
            handle.write(json.dumps(chunk.__dict__, ensure_ascii=True) + "\n")

    report = {
        "status": "ok" if prepared_chunks else "warn",
        "manifest": str(manifest_path),
        "source_count": len(sources),
        "chunk_count": len(prepared_chunks),
        "source_reports": source_reports,
        "errors": errors,
        "output": str(output_path),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info(
        "Legal KB preparation complete",
        sources=len(sources),
        chunks=len(prepared_chunks),
        report=str(report_path),
    )


if __name__ == "__main__":
    main()
