"""Generate human-annotation packets for similar-case retrieval evaluation.

Source records are read from an existing eval JSONL file and expanded using live API
responses to produce reviewer-friendly query/candidate packets.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from src.config.settings import settings


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for packet generation."""
    parser = argparse.ArgumentParser(
        description="Generate human-annotation packets for retrieval eval"
    )
    parser.add_argument(
        "--source-file",
        type=str,
        default="data/evals/similar_cases_gold.jsonl",
        help="Input eval JSONL path",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="data/evals/similar_cases_human_packets.jsonl",
        help="Output annotation packet JSONL path",
    )
    parser.add_argument(
        "--queries",
        type=int,
        default=150,
        help="Number of query packets to generate",
    )
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed")
    parser.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="Candidates per query fetched from similar endpoint",
    )
    parser.add_argument(
        "--similarity-mode",
        type=str,
        default="",
        choices=["", "combined", "factual", "legal", "fulltext"],
        help="Override similarity mode for all packets",
    )
    return parser.parse_args()


def load_source_records(path: Path) -> list[dict[str, Any]]:
    """Load JSONL records from source file."""
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        if "query_case_id" in item:
            records.append(item)
    return records


def _build_base_url() -> str:
    """Build local API base URL from settings."""
    api_host = settings.api_host if settings.api_host != "0.0.0.0" else "localhost"
    return f"http://{api_host}:{settings.api_port}/api/v1/cases"


def _excerpt(text: str, limit: int = 1200) -> str:
    """Return trimmed text excerpt for annotation packet."""
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit] + " ..."


def build_packet(
    record: dict[str, Any],
    client: httpx.Client,
    base_url: str,
    top_k: int,
    override_mode: str,
) -> dict[str, Any]:
    """Build one annotation packet from a query-case record."""
    query_case_id = int(record["query_case_id"])
    mode = override_mode or str(record.get("similarity_mode", "combined"))

    query_response = client.get(f"{base_url}/{query_case_id}")
    query_response.raise_for_status()
    query_payload = query_response.json()

    similar_response = client.get(
        f"{base_url}/{query_case_id}/similar",
        params={"top_k": top_k, "similarity_mode": mode},
    )
    similar_response.raise_for_status()
    similar_payload = similar_response.json()

    query_summary = {
        "case_id": query_payload.get("case_id"),
        "case_title": query_payload.get("case_title", ""),
        "court": query_payload.get("court", ""),
        "date_of_judgment": query_payload.get("date_of_judgment"),
        "case_type": query_payload.get("case_type", ""),
        "verdict": query_payload.get("verdict", ""),
        "sections_invoked": query_payload.get("sections_invoked", []) or [],
        "headnotes": (query_payload.get("headnotes", []) or [])[:5],
        "full_text_excerpt": _excerpt(str(query_payload.get("full_text", ""))),
    }

    candidates = []
    for item in similar_payload.get("results", []):
        candidates.append(
            {
                "rank": item.get("rank"),
                "case_id": item.get("case_id"),
                "case_title": item.get("case_title", ""),
                "court": item.get("court", ""),
                "date_of_judgment": item.get("date_of_judgment"),
                "case_type": item.get("case_type", ""),
                "verdict": item.get("verdict", ""),
                "combined_score": item.get("combined_score", 0.0),
                "sections_invoked": item.get("sections_invoked", []) or [],
                "statutes_cited": item.get("statutes_cited", []) or [],
                "similarity_explanation": item.get("similarity_explanation", ""),
                "label": None,
                "note": "",
            }
        )

    return {
        "query_id": str(record.get("query_id") or f"case_{query_case_id}"),
        "query_case_id": query_case_id,
        "similarity_mode": mode,
        "query": query_summary,
        "candidates": candidates,
    }


def main() -> None:
    """Generate annotation packets and persist as JSONL."""
    args = parse_args()
    random.seed(args.seed)

    source_path = Path(args.source_file)
    output_path = Path(args.output_file)
    records = load_source_records(source_path)
    if not records:
        logger.warning("No source records found", source=str(source_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("", encoding="utf-8")
        return

    random.shuffle(records)
    picked = records[: max(0, args.queries)]

    base_url = _build_base_url()
    packets: list[dict[str, Any]] = []
    with httpx.Client(timeout=120) as client:
        for record in picked:
            try:
                packet = build_packet(
                    record,
                    client,
                    base_url=base_url,
                    top_k=args.top_k,
                    override_mode=args.similarity_mode,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to build annotation packet",
                    query_id=str(record.get("query_id", "unknown")),
                    error=str(exc),
                )
                continue
            packets.append(packet)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for packet in packets:
            file.write(json.dumps(packet) + "\n")

    logger.info(
        "Human eval packets generated",
        packets=len(packets),
        source=str(source_path),
        output=str(output_path),
    )


if __name__ == "__main__":
    main()
