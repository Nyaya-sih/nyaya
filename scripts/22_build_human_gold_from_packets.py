"""Build human-gold eval JSONL from labeled annotation packets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from loguru import logger


def parse_args() -> argparse.Namespace:
    """Parse CLI args for packet-to-gold conversion."""
    parser = argparse.ArgumentParser(
        description="Convert labeled annotation packets to human-gold JSONL"
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
        default="data/evals/similar_cases_human_gold.jsonl",
        help="Output human-gold JSONL path",
    )
    parser.add_argument(
        "--min-judgments",
        type=int,
        default=3,
        help="Minimum labeled candidates required per query",
    )
    return parser.parse_args()


def _normalize_label(value: Any) -> int | None:
    """Normalize annotation label to 0/1/2 or None."""
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


def load_packets(path: Path) -> list[dict[str, Any]]:
    """Load packet JSONL records."""
    if not path.exists():
        return []
    packets = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        packets.append(json.loads(line))
    return packets


def to_gold_record(packet: dict[str, Any], min_judgments: int) -> dict[str, Any] | None:
    """Convert one packet to human-gold schema if sufficiently labeled."""
    candidates = packet.get("candidates", [])
    if not isinstance(candidates, list):
        return None

    judgments = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or "case_id" not in candidate:
            continue
        label = _normalize_label(candidate.get("label"))
        if label is None:
            continue
        judgments.append(
            {
                "case_id": int(candidate["case_id"]),
                "label": label,
                "note": str(candidate.get("note", "")).strip(),
            }
        )

    if len(judgments) < min_judgments:
        return None

    return {
        "query_id": str(packet.get("query_id", "unknown")),
        "query_case_id": int(packet.get("query_case_id")),
        "similarity_mode": str(packet.get("similarity_mode", "fulltext")),
        "judgments": judgments,
    }


def main() -> None:
    """Generate human-gold JSONL from labeled packets."""
    args = parse_args()
    packets_path = Path(args.packets_file)
    output_path = Path(args.output_file)

    packets = load_packets(packets_path)
    if not packets:
        logger.warning("No packets found", path=str(packets_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("", encoding="utf-8")
        return

    rows = []
    for packet in packets:
        row = to_gold_record(packet, min_judgments=args.min_judgments)
        if row is not None:
            rows.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row) + "\n")

    logger.info(
        "Human gold file generated",
        packets=len(packets),
        rows=len(rows),
        path=str(output_path),
    )


if __name__ == "__main__":
    main()
