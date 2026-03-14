"""Merge reviewer annotation batches and emit conflict report."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from loguru import logger


def parse_args() -> argparse.Namespace:
    """Parse CLI args for batch merge workflow."""
    parser = argparse.ArgumentParser(
        description="Merge reviewer JSONL batches into one packet file"
    )
    parser.add_argument(
        "--batches-dir",
        type=str,
        default="data/evals/human_batches",
        help="Directory containing reviewer_*.jsonl files",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="reviewer_*.jsonl",
        help="Glob pattern for reviewer files",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="data/evals/similar_cases_human_packets_merged.jsonl",
        help="Output merged packet JSONL path",
    )
    parser.add_argument(
        "--conflict-report",
        type=str,
        default="data/processed/human_annotation_conflicts.json",
        help="Output conflict report JSON path",
    )
    return parser.parse_args()


def normalize_label(value: Any) -> int | None:
    """Normalize labels to 0/1/2 or None when missing/invalid."""
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


def to_int(value: Any, default: int = 0) -> int:
    """Convert arbitrary value to int with fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_reviewer_batches(
    batches_dir: Path, pattern: str
) -> dict[str, list[dict[str, Any]]]:
    """Load reviewer files from a directory using pattern."""
    files = sorted(batches_dir.glob(pattern))
    batches: dict[str, list[dict[str, Any]]] = {}
    for file_path in files:
        reviewer = file_path.stem.replace("reviewer_", "")
        rows = []
        for line in file_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        batches[reviewer] = rows
    return batches


def _query_key(packet: dict[str, Any]) -> tuple[str, int]:
    """Build stable query key from packet identifiers."""
    query_case_id_int = to_int(packet.get("query_case_id"), default=0)
    return (str(packet.get("query_id", "unknown")), query_case_id_int)


def merge_batches(
    batches: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Merge reviewer batches and return merged packets + conflict report."""
    base_packets: dict[tuple[str, int], dict[str, Any]] = {}
    votes: dict[tuple[tuple[str, int], int], list[dict[str, Any]]] = {}

    for reviewer, packets in batches.items():
        for packet in packets:
            key = _query_key(packet)
            if key not in base_packets:
                base_packets[key] = packet

            for candidate in packet.get("candidates", []) or []:
                if not isinstance(candidate, dict) or "case_id" not in candidate:
                    continue
                label = normalize_label(candidate.get("label"))
                if label is None:
                    continue
                vote_key = (key, to_int(candidate.get("case_id"), default=0))
                votes.setdefault(vote_key, []).append(
                    {
                        "reviewer": reviewer,
                        "label": label,
                        "note": str(candidate.get("note", "")).strip(),
                    }
                )

    conflicts = []
    annotated_candidates = 0
    resolved_candidates = 0
    merged_packets: list[dict[str, Any]] = []

    for key, packet in sorted(base_packets.items(), key=lambda item: item[0]):
        merged_packet = json.loads(json.dumps(packet))
        for candidate in merged_packet.get("candidates", []) or []:
            if not isinstance(candidate, dict) or "case_id" not in candidate:
                continue
            vote_key = (key, to_int(candidate.get("case_id"), default=0))
            candidate_votes = votes.get(vote_key, [])
            if not candidate_votes:
                continue

            annotated_candidates += 1
            label_counts = Counter(v["label"] for v in candidate_votes)
            ordered = label_counts.most_common()

            if len(ordered) == 1 or (
                len(ordered) > 1 and ordered[0][1] > ordered[1][1]
            ):
                selected_label = int(ordered[0][0])
                selected_note = ""
                for vote in candidate_votes:
                    if vote["label"] == selected_label and vote["note"]:
                        selected_note = vote["note"]
                        break
                candidate["label"] = selected_label
                candidate["note"] = selected_note
                resolved_candidates += 1
            else:
                candidate["label"] = None
                candidate["note"] = ""
                conflicts.append(
                    {
                        "query_id": key[0],
                        "query_case_id": key[1],
                        "candidate_case_id": to_int(
                            candidate.get("case_id"), default=0
                        ),
                        "votes": candidate_votes,
                        "label_counts": {
                            str(k): int(v) for k, v in label_counts.items()
                        },
                    }
                )

        merged_packets.append(merged_packet)

    report = {
        "summary": {
            "reviewers": len(batches),
            "queries": len(base_packets),
            "annotated_candidates": annotated_candidates,
            "resolved_candidates": resolved_candidates,
            "conflicts": len(conflicts),
        },
        "conflicts": conflicts,
    }
    return merged_packets, report


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSONL rows to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row) + "\n")


def main() -> None:
    """Run merge and write merged packets + conflict report."""
    args = parse_args()
    batches = load_reviewer_batches(Path(args.batches_dir), args.pattern)
    merged_packets, report = merge_batches(batches)

    output_file = Path(args.output_file)
    conflict_file = Path(args.conflict_report)
    write_jsonl(output_file, merged_packets)
    conflict_file.parent.mkdir(parents=True, exist_ok=True)
    conflict_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info(
        "Merged annotation batches",
        reviewers=report["summary"]["reviewers"],
        queries=report["summary"]["queries"],
        conflicts=report["summary"]["conflicts"],
        merged_file=str(output_file),
        conflict_report=str(conflict_file),
    )


if __name__ == "__main__":
    main()
