"""Validate human annotation packet completeness and label quality."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from loguru import logger


def parse_args() -> argparse.Namespace:
    """Parse CLI args for annotation validation."""
    parser = argparse.ArgumentParser(
        description="Validate labeled human annotation packets"
    )
    parser.add_argument(
        "--packets-file",
        type=str,
        default="data/evals/similar_cases_human_packets.jsonl",
        help="Input packets JSONL path",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="data/processed/human_annotation_report.json",
        help="Output validation report JSON path",
    )
    parser.add_argument(
        "--min-labeled-per-query",
        type=int,
        default=3,
        help="Minimum labeled candidates required per query",
    )
    return parser.parse_args()


def load_packets(path: Path) -> list[dict[str, Any]]:
    """Load annotation packets JSONL."""
    if not path.exists():
        return []
    packets = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        packets.append(json.loads(line))
    return packets


def _normalize_label(value: Any) -> int | None:
    """Normalize label to 0/1/2 if present."""
    if value is None or value == "":
        return None
    try:
        label = int(value)
    except (TypeError, ValueError):
        return None
    if label < 0:
        return 0
    if label > 2:
        return 2
    return label


def validate_packets(
    packets: list[dict[str, Any]], min_labeled_per_query: int
) -> dict[str, Any]:
    """Produce validation metrics and pass/fail status."""
    if not packets:
        return {
            "status": "warn",
            "summary": {
                "total_queries": 0,
                "queries_with_any_labels": 0,
                "queries_meeting_min_labels": 0,
                "total_labeled_candidates": 0,
            },
            "label_distribution": {"0": 0, "1": 0, "2": 0},
            "issues": ["No packets found."],
        }

    total_queries = len(packets)
    queries_with_any_labels = 0
    queries_meeting_min_labels = 0
    total_labeled_candidates = 0
    label_distribution = {0: 0, 1: 0, 2: 0}
    issues: list[str] = []

    for packet in packets:
        query_id = str(packet.get("query_id", "unknown"))
        candidates = packet.get("candidates", [])
        if not isinstance(candidates, list):
            issues.append(f"{query_id}: candidates is not a list")
            continue

        labeled_for_query = 0
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            label = _normalize_label(candidate.get("label"))
            if label is None:
                continue
            labeled_for_query += 1
            total_labeled_candidates += 1
            label_distribution[label] += 1

        if labeled_for_query > 0:
            queries_with_any_labels += 1
        if labeled_for_query >= min_labeled_per_query:
            queries_meeting_min_labels += 1
        elif labeled_for_query > 0:
            issues.append(
                f"{query_id}: only {labeled_for_query} labels (min {min_labeled_per_query})"
            )

    completion_ratio = (
        queries_meeting_min_labels / total_queries if total_queries > 0 else 0.0
    )
    status = "pass" if completion_ratio >= 0.9 else "warn"

    if label_distribution[1] == 0 and label_distribution[2] == 0:
        issues.append("No positive labels (1/2) found yet.")

    return {
        "status": status,
        "summary": {
            "total_queries": total_queries,
            "queries_with_any_labels": queries_with_any_labels,
            "queries_meeting_min_labels": queries_meeting_min_labels,
            "total_labeled_candidates": total_labeled_candidates,
            "completion_ratio": completion_ratio,
            "min_labeled_per_query": min_labeled_per_query,
        },
        "label_distribution": {
            "0": label_distribution[0],
            "1": label_distribution[1],
            "2": label_distribution[2],
        },
        "issues": issues,
    }


def main() -> None:
    """Run validation and persist report JSON."""
    args = parse_args()
    packets_path = Path(args.packets_file)
    output_path = Path(args.output_file)

    packets = load_packets(packets_path)
    report = validate_packets(packets, min_labeled_per_query=args.min_labeled_per_query)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info(
        "Human annotation validation complete",
        status=report.get("status"),
        total_queries=report.get("summary", {}).get("total_queries", 0),
        completion_ratio=report.get("summary", {}).get("completion_ratio", 0.0),
        path=str(output_path),
    )


if __name__ == "__main__":
    main()
