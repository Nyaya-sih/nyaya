"""Export reviewer-specific annotation packet subsets."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from loguru import logger


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for reviewer batch export."""
    parser = argparse.ArgumentParser(
        description="Split annotation packets into reviewer-specific JSONL files"
    )
    parser.add_argument(
        "--packets-file",
        type=str,
        default="data/evals/similar_cases_human_packets.jsonl",
        help="Input packets JSONL path",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/evals/human_batches",
        help="Directory to write reviewer batch files",
    )
    parser.add_argument(
        "--reviewers",
        type=str,
        default="A,B,C",
        help="Comma-separated reviewer IDs",
    )
    parser.add_argument(
        "--overlap-percent",
        type=float,
        default=10.0,
        help="Percent of total packets duplicated to all reviewers for adjudication",
    )
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed")
    return parser.parse_args()


def parse_reviewers(text: str) -> list[str]:
    """Parse comma-separated reviewer IDs."""
    reviewers = [part.strip() for part in text.split(",") if part.strip()]
    if not reviewers:
        return ["A"]
    return reviewers


def load_packets(path: Path) -> list[dict[str, Any]]:
    """Load annotation packet JSONL file."""
    if not path.exists():
        return []
    packets = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        packets.append(json.loads(line))
    return packets


def split_packets(
    packets: list[dict[str, Any]],
    reviewers: list[str],
    overlap_percent: float,
    seed: int,
) -> dict[str, list[dict[str, Any]]]:
    """Split packets by reviewer with optional shared overlap set."""
    random.seed(seed)
    shuffled = list(packets)
    random.shuffle(shuffled)

    if overlap_percent < 0:
        overlap_percent = 0.0
    if overlap_percent > 100:
        overlap_percent = 100.0
    overlap_count = int(round(len(shuffled) * (overlap_percent / 100.0)))
    overlap = shuffled[:overlap_count]
    remainder = shuffled[overlap_count:]

    assignments = {reviewer: list(overlap) for reviewer in reviewers}
    for idx, packet in enumerate(remainder):
        reviewer = reviewers[idx % len(reviewers)]
        assignments[reviewer].append(packet)
    return assignments


def write_batches(
    output_dir: Path, assignments: dict[str, list[dict[str, Any]]]
) -> None:
    """Write reviewer-specific JSONL files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for reviewer, packets in assignments.items():
        output_path = output_dir / f"reviewer_{reviewer}.jsonl"
        with output_path.open("w", encoding="utf-8") as file:
            for packet in packets:
                file.write(json.dumps(packet) + "\n")


def main() -> None:
    """Export reviewer annotation batches."""
    args = parse_args()
    packets_path = Path(args.packets_file)
    output_dir = Path(args.output_dir)
    reviewers = parse_reviewers(args.reviewers)

    packets = load_packets(packets_path)
    assignments = split_packets(
        packets,
        reviewers=reviewers,
        overlap_percent=args.overlap_percent,
        seed=args.seed,
    )
    write_batches(output_dir, assignments)

    logger.info(
        "Reviewer batches exported",
        packets=len(packets),
        reviewers=len(reviewers),
        overlap_percent=args.overlap_percent,
        output_dir=str(output_dir),
    )


if __name__ == "__main__":
    main()
