"""Generate structured legal KB chunks from fetched raw files.

Reads: legal_kb/fetch_manifest.json
Writes:
- legal_kb/chunks/<act_slug>.jsonl
- legal_kb/chunks/index.json
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

import pdfplumber
import PyPDF2


MANIFEST_PATH = Path("legal_kb/fetch_manifest.json")
CHUNKS_DIR = Path("legal_kb/chunks")


EXECUTION_ORDER = [
    # 1. Constitution
    "constitution_of_india",
    # 2. Tier 0 statutes
    "bharatiya_nyaya_sanhita_2023",
    "bharatiya_nagarik_suraksha_sanhita_2023",
    "bharatiya_sakshya_adhiniyam_2023",
    "indian_penal_code_1860",
    "code_of_criminal_procedure_1973",
    "indian_evidence_act_1872",
    "code_of_civil_procedure_1908",
    # 3. Tier 1 statutes
    "indian_contract_act_1872",
    "transfer_of_property_act_1882",
    "specific_relief_act_1963",
    "limitation_act_1963",
    "companies_act_2013",
    "information_technology_act_2000",
    "consumer_protection_act_2019",
    "rti_act_2005",
    "motor_vehicles_act_1988",
    "pocso_act_2012",
    "prevention_of_corruption_act_1988",
    "arbitration_and_conciliation_act_1996",
    "insolvency_and_bankruptcy_code_2016",
    # 4. Tier 2 procedural docs
    "supreme_court_rules_2013",
    "delhi_high_court_rules",
    "bombay_high_court_rules",
    "patna_high_court_rules",
    "civil_rules_of_practice",
    "criminal_rules_of_practice",
    "cpc_bnss_procedural_mapping_notes",
    # 5. Tier 3 secondary + glossary
    "law_commission_report_47",
    "law_commission_report_69",
    "law_commission_report_152",
    "law_commission_report_172",
    "law_commission_report_177",
    "law_commission_report_198",
    "law_commission_report_227",
    "law_commission_report_239",
    "law_commission_report_248",
    "law_commission_report_262",
    "law_commission_report_277",
    "law_commission_report_279",
    "njdg_procedural_guides",
    "bar_council_of_india_rules",
    "legal_maxims_glossary",
]


MAPPED_SECTIONS = {
    # Keep only mappings that are confidently known; default is null.
    # Intentionally sparse to avoid incorrect legal mapping guesses.
}


def normalize_text(text: str) -> str:
    """Normalize whitespace and remove obvious non-content artifacts."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if re.match(r"^\d{1,4}$", stripped):
            continue
        if re.search(
            r"download india code logo|site designed and developed", stripped, re.I
        ):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def read_pdf_text(path: Path) -> str:
    """Extract text from PDF using pdfplumber, fallback to PyPDF2."""
    try:
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return normalize_text("\n\n".join(pages))
    except Exception:
        pass

    try:
        pages = []
        with open(path, "rb") as handle:
            reader = PyPDF2.PdfReader(handle)
            for page in reader.pages:
                pages.append(page.extract_text() or "")
        return normalize_text("\n\n".join(pages))
    except Exception:
        return ""


def read_html_text(path: Path) -> str:
    """Extract substantive text from HTML fallback pages."""
    raw = path.read_text(encoding="utf-8", errors="ignore")
    # Remove major non-content blocks.
    raw = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style.*?>.*?</style>", " ", raw)
    raw = re.sub(r"(?is)<nav.*?>.*?</nav>", " ", raw)
    raw = re.sub(r"(?is)<header.*?>.*?</header>", " ", raw)
    raw = re.sub(r"(?is)<footer.*?>.*?</footer>", " ", raw)
    raw = re.sub(r"(?is)<aside.*?>.*?</aside>", " ", raw)
    raw = re.sub(r"(?is)<[^>]+>", "\n", raw)
    raw = raw.replace("&nbsp;", " ").replace("&amp;", "&")
    return normalize_text(raw)


def read_md_text(path: Path) -> str:
    """Read markdown/plain text."""
    return normalize_text(path.read_text(encoding="utf-8", errors="ignore"))


def load_source_text(file_path: Path) -> str:
    """Load and normalize source text by extension."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf_text(file_path)
    if suffix in {".html", ".htm"}:
        return read_html_text(file_path)
    if suffix in {".md", ".txt"}:
        return read_md_text(file_path)
    return ""


def estimate_tokens(text: str) -> int:
    """Estimate token count using requested rough conversion."""
    return int(math.ceil(len(text.split()) * 1.35))


def hash_text(text: str) -> str:
    """SHA-256 of chunk text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def jurisdiction_for_slug(slug: str) -> str:
    """Infer jurisdiction by act slug."""
    if slug == "delhi_high_court_rules":
        return "state:delhi"
    if slug == "bombay_high_court_rules":
        return "state:maharashtra"
    if slug == "patna_high_court_rules":
        return "state:bihar"
    return "central"


def source_type_for_entry(slug: str, tier: int) -> str:
    """Map entry to requested source_type enum."""
    if slug == "constitution_of_india":
        return "constitution"
    if slug == "legal_maxims_glossary":
        return "glossary"
    if slug.startswith("law_commission_report_") or slug in {
        "njdg_procedural_guides",
        "bar_council_of_india_rules",
    }:
        return "secondary_source"
    if tier == 2:
        if "high_court" in slug or "supreme_court_rules" in slug:
            return "court_rule"
        return "procedural_rule"
    return "statute"


def split_by_statute_sections(text: str) -> list[dict[str, str]]:
    """Split statutes into section chunks with chapter context."""
    lines = text.split("\n")
    sec_re = re.compile(
        r"^\s*(?:section|sec\.?|s\.)\s*([0-9]+[A-Za-z]?)\b[\.:\-\)]?\s*(.*)$", re.I
    )
    chap_re = re.compile(r"^\s*(chapter|part)\s+([IVXLC0-9A-Za-z\-]+)\b\s*(.*)$", re.I)

    chapter_or_part = ""
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for line in lines:
        chapter_match = chap_re.match(line.strip())
        if chapter_match:
            kind = chapter_match.group(1).title()
            ident = chapter_match.group(2).strip()
            title = chapter_match.group(3).strip()
            chapter_or_part = f"{kind} {ident}" + (f" - {title}" if title else "")
            continue

        section_match = sec_re.match(line.strip())
        if section_match:
            if current is not None:
                blocks.append(current)
            sec_no = section_match.group(1).strip()
            sec_title = section_match.group(2).strip()
            current = {
                "section_or_article": f"Section {sec_no}",
                "section_key": sec_no,
                "section_title": sec_title,
                "chapter_or_part": chapter_or_part,
                "body": "",
            }
            continue

        if current is not None:
            current["body"] += line + "\n"

    if current is not None:
        blocks.append(current)

    if not blocks:
        # Fallback: one document-like section
        return [
            {
                "section_or_article": "Section 1",
                "section_key": "1",
                "section_title": "",
                "chapter_or_part": "",
                "body": text,
            }
        ]

    return blocks


def split_constitution(text: str) -> list[dict[str, str]]:
    """Split constitution into Articles and Schedules."""
    lines = text.split("\n")
    art_re = re.compile(r"^\s*article\s+([0-9]+[A-Za-z]?)\b[\.:\-\)]?\s*(.*)$", re.I)
    sch_re = re.compile(
        r"^\s*((?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|[0-9]+(?:st|nd|rd|th))\s+schedule\b.*)$",
        re.I,
    )

    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for line in lines:
        article_match = art_re.match(line.strip())
        schedule_match = sch_re.match(line.strip())

        if article_match:
            if current is not None:
                blocks.append(current)
            no = article_match.group(1).strip()
            title = article_match.group(2).strip()
            current = {
                "kind": "article",
                "section_or_article": f"Article {no}",
                "section_key": no,
                "section_title": title,
                "chapter_or_part": "",
                "body": "",
            }
            continue

        if schedule_match:
            if current is not None:
                blocks.append(current)
            label = schedule_match.group(1).strip()
            sch_no_match = re.match(r"([A-Za-z0-9]+)", label)
            sch_no = sch_no_match.group(1) if sch_no_match else "1"
            current = {
                "kind": "schedule",
                "section_or_article": f"Schedule {label}",
                "section_key": sch_no,
                "section_title": label,
                "chapter_or_part": "",
                "body": "",
            }
            continue

        if current is not None:
            current["body"] += line + "\n"

    if current is not None:
        blocks.append(current)

    if not blocks:
        return [
            {
                "kind": "article",
                "section_or_article": "Article 1",
                "section_key": "1",
                "section_title": "",
                "chapter_or_part": "",
                "body": text,
            }
        ]

    return blocks


def split_order_rules(text: str) -> list[dict[str, str]]:
    """Split procedural/court rules into Order+Rule units."""
    lines = text.split("\n")
    order_re = re.compile(r"^\s*order\s+([IVXLC0-9A-Za-z\-]+)\b\s*(.*)$", re.I)
    rule_re = re.compile(r"^\s*rule\s+([0-9A-Za-z\-]+)\b[\.:\-\)]?\s*(.*)$", re.I)

    current_order = ""
    current_order_title = ""
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for line in lines:
        om = order_re.match(line.strip())
        if om:
            current_order = om.group(1).strip()
            current_order_title = om.group(2).strip()
            continue

        rm = rule_re.match(line.strip())
        if rm:
            if current is not None:
                blocks.append(current)
            rule_no = rm.group(1).strip()
            rule_title = rm.group(2).strip()
            current = {
                "section_or_article": f"Order {current_order} Rule {rule_no}".strip(),
                "order_no": current_order or "1",
                "rule_no": rule_no,
                "section_title": rule_title,
                "chapter_or_part": (
                    f"Order {current_order}"
                    + (f" - {current_order_title}" if current_order_title else "")
                ).strip(),
                "body": "",
            }
            continue

        if current is not None:
            current["body"] += line + "\n"

    if current is not None:
        blocks.append(current)

    if blocks:
        return blocks

    # Fallback to statute-like splitting.
    as_sections = split_by_statute_sections(text)
    converted = []
    for item in as_sections:
        converted.append(
            {
                "section_or_article": item["section_or_article"],
                "order_no": "1",
                "rule_no": item["section_key"],
                "section_title": item["section_title"],
                "chapter_or_part": item["chapter_or_part"],
                "body": item["body"],
            }
        )
    return converted


def split_report_sections(text: str) -> list[dict[str, str]]:
    """Split law commission report by numbered heading blocks."""
    lines = text.split("\n")
    heading_re = re.compile(
        r"^\s*((?:chapter\s+[ivxlcdm0-9]+|[0-9]+(?:\.[0-9]+)*))\s*[\.:\-\)]?\s*(.*)$",
        re.I,
    )
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for line in lines:
        hm = heading_re.match(line.strip())
        if hm and len(line.strip()) < 180:
            if current is not None:
                blocks.append(current)
            label = hm.group(1).strip()
            title = hm.group(2).strip()
            key = re.sub(r"[^0-9A-Za-z]+", "_", label).strip("_") or "1"
            current = {
                "section_or_article": f"Section {label}",
                "section_key": key,
                "section_title": title,
                "chapter_or_part": "",
                "body": "",
            }
            continue
        if current is not None:
            current["body"] += line + "\n"

    if current is not None:
        blocks.append(current)

    if not blocks:
        return [
            {
                "section_or_article": "Section 1",
                "section_key": "1",
                "section_title": "",
                "chapter_or_part": "",
                "body": text,
            }
        ]
    return blocks


def split_glossary(text: str) -> list[dict[str, str]]:
    """Split markdown glossary into one chunk per maxim entry."""
    entries = []
    pattern = re.compile(
        r"^\s*(\d+)\.\s*\*\*(.+?)\*\*\s*-\s*(.+?)\s*-\s*Example:\s*(.+?)$", re.M
    )
    for match in pattern.finditer(text):
        idx = int(match.group(1))
        maxim = match.group(2).strip()
        meaning = match.group(3).strip()
        usage = match.group(4).strip()
        entries.append(
            {
                "idx": idx,
                "section_or_article": maxim,
                "section_title": maxim,
                "chapter_or_part": "",
                "body": f"{maxim}\nMeaning: {meaning}\nUsage: {usage}",
            }
        )
    return entries


def split_long_section(body: str, max_token_estimate: int = 600) -> list[str]:
    """Split very long section text at subsection boundaries."""
    token_est = estimate_tokens(body)
    if token_est <= max_token_estimate:
        return [body]

    parts = re.split(r"(?m)(?=^\s*\([0-9]+\)\s*)", body)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= 1:
        # Fallback hard split by paragraphs.
        paras = [p.strip() for p in body.split("\n\n") if p.strip()]
        parts = paras if paras else [body]

    chunks = []
    current = ""
    for segment in parts:
        candidate = (current + "\n" + segment).strip() if current else segment
        if estimate_tokens(candidate) > max_token_estimate and current:
            chunks.append(current.strip())
            current = segment
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks


def build_base_chunk(entry: dict[str, Any], source_type: str) -> dict[str, Any]:
    """Common fields for all chunk records."""
    return {
        "act_name": entry["act_name"],
        "act_slug": entry["act_slug"],
        "year": entry.get("year") if entry.get("year") is not None else 0,
        "tier": int(entry.get("tier") or 0),
        "jurisdiction": jurisdiction_for_slug(entry["act_slug"]),
        "source_type": source_type,
        "is_superseded": bool(entry.get("is_superseded", False)),
        "superseded_by": entry.get("superseded_by"),
        "source_url": entry.get("source_url") or "",
    }


def chunk_entry(entry: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """Generate chunks for one manifest entry.

    Returns: (chunks, parse_error)
    """
    src_path = Path(entry["file_path"])
    if not src_path.exists():
        return [], f"source file missing: {src_path}"

    text = load_source_text(src_path)
    if not text.strip():
        return [], f"empty extracted text: {src_path}"

    slug = entry["act_slug"]
    tier = int(entry.get("tier") or 0)
    source_type = source_type_for_entry(slug, tier)
    base = build_base_chunk(entry, source_type)

    out_chunks: list[dict[str, Any]] = []

    if slug == "legal_maxims_glossary":
        items = split_glossary(text)
        for item in items:
            idx = int(item["idx"])
            chunk_text = normalize_text(item["body"])
            record = {
                **base,
                "chunk_id": f"glossary_maxim_{idx:03d}",
                "section_or_article": item["section_or_article"],
                "section_title": item["section_title"],
                "chapter_or_part": item["chapter_or_part"],
                "chunk_text": chunk_text,
            }
            record["source_version_hash"] = hash_text(record["chunk_text"])
            record["token_estimate"] = estimate_tokens(record["chunk_text"])
            out_chunks.append(record)
        return out_chunks, None if out_chunks else "no glossary entries parsed"

    if slug == "constitution_of_india":
        blocks = split_constitution(text)
        for block in blocks:
            kind = block.get("kind", "article")
            key = block.get("section_key", "1")
            chunk_prefix = (
                "constitution_art" if kind == "article" else "constitution_sch"
            )
            chunk_text = "\n".join(
                part
                for part in [
                    block.get("chapter_or_part", "").strip(),
                    f"{block['section_or_article']}. {block.get('section_title', '').strip()}".strip(),
                    block.get("body", "").strip()
                    or f"{block['section_or_article']} [Repealed]",
                ]
                if part
            ).strip()
            chunk_text = normalize_text(chunk_text)
            record = {
                **base,
                "chunk_id": f"{chunk_prefix}{key}",
                "section_or_article": block["section_or_article"],
                "section_title": block.get("section_title", ""),
                "chapter_or_part": block.get("chapter_or_part", ""),
                "chunk_text": chunk_text,
            }
            if not (block.get("body") or "").strip():
                record["is_repealed"] = True
            record["source_version_hash"] = hash_text(record["chunk_text"])
            record["token_estimate"] = estimate_tokens(record["chunk_text"])
            out_chunks.append(record)
        return out_chunks, None

    if source_type in {"court_rule", "procedural_rule"}:
        blocks = split_order_rules(text)
        for block in blocks:
            order_no = re.sub(r"[^0-9A-Za-z]+", "", block.get("order_no", "1")) or "1"
            rule_no = re.sub(r"[^0-9A-Za-z]+", "", block.get("rule_no", "1")) or "1"
            chunk_text = "\n".join(
                part
                for part in [
                    block.get("chapter_or_part", "").strip(),
                    f"{block['section_or_article']}. {block.get('section_title', '').strip()}".strip(),
                    block.get("body", "").strip()
                    or f"{block['section_or_article']} [Repealed]",
                ]
                if part
            ).strip()
            chunk_text = normalize_text(chunk_text)
            record = {
                **base,
                "chunk_id": f"{slug}_ord{order_no}_r{rule_no}",
                "section_or_article": block["section_or_article"],
                "section_title": block.get("section_title", ""),
                "chapter_or_part": block.get("chapter_or_part", ""),
                "chunk_text": chunk_text,
            }
            if not (block.get("body") or "").strip():
                record["is_repealed"] = True
            record["source_version_hash"] = hash_text(record["chunk_text"])
            record["token_estimate"] = estimate_tokens(record["chunk_text"])
            out_chunks.append(record)
        return out_chunks, None

    if source_type == "secondary_source" and slug.startswith("law_commission_report_"):
        blocks = split_report_sections(text)
        report_no = slug.split("_")[-1]
        for block in blocks:
            key = block.get("section_key", "1")
            chunk_text = "\n".join(
                part
                for part in [
                    block.get("chapter_or_part", "").strip(),
                    f"{block['section_or_article']}. {block.get('section_title', '').strip()}".strip(),
                    block.get("body", "").strip()
                    or f"{block['section_or_article']} [Repealed]",
                ]
                if part
            ).strip()
            chunk_text = normalize_text(chunk_text)
            record = {
                **base,
                "chunk_id": f"lcr_{report_no}_s{key}",
                "section_or_article": block["section_or_article"],
                "section_title": block.get("section_title", ""),
                "chapter_or_part": block.get("chapter_or_part", ""),
                "chunk_text": chunk_text,
            }
            if not (block.get("body") or "").strip():
                record["is_repealed"] = True
            record["source_version_hash"] = hash_text(record["chunk_text"])
            record["token_estimate"] = estimate_tokens(record["chunk_text"])
            out_chunks.append(record)
        return out_chunks, None

    # Default: statutes + remaining secondary sources chunked by section-like units.
    blocks = split_by_statute_sections(text)
    for block in blocks:
        sec_key = block.get("section_key", "1")
        body = block.get("body", "").strip()
        body_parts = split_long_section(body, max_token_estimate=600)

        for idx, body_part in enumerate(body_parts, start=1):
            section_text = (
                body_part.strip() or f"{block['section_or_article']} [Repealed]"
            )
            header_bits = []
            if block.get("chapter_or_part", "").strip():
                header_bits.append(block["chapter_or_part"].strip())
            header_bits.append(
                f"{block['section_or_article']}. {block.get('section_title', '').strip()}".strip()
            )
            chunk_text = normalize_text("\n".join(header_bits + [section_text]))

            if len(body_parts) > 1:
                chunk_id = f"{slug}_s{sec_key}_part{idx}"
            else:
                chunk_id = f"{slug}_s{sec_key}"

            record = {
                **base,
                "chunk_id": chunk_id,
                "section_or_article": block["section_or_article"],
                "section_title": block.get("section_title", ""),
                "chapter_or_part": block.get("chapter_or_part", ""),
                "chunk_text": chunk_text,
            }

            if not body.strip():
                record["is_repealed"] = True

            if base["is_superseded"]:
                mapped = MAPPED_SECTIONS.get((slug, sec_key.upper()))
                record["mapped_to"] = mapped if mapped is not None else None

            record["source_version_hash"] = hash_text(record["chunk_text"])
            record["token_estimate"] = estimate_tokens(record["chunk_text"])
            out_chunks.append(record)

    return out_chunks, None


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write rows as compact JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n"
            )


def main() -> None:
    """Generate chunk files and index."""
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")

    manifest: list[dict[str, Any]] = json.loads(
        MANIFEST_PATH.read_text(encoding="utf-8")
    )
    active = [
        row
        for row in manifest
        if row.get("fetch_status") in {"success", "fallback_used"}
    ]
    by_slug = {row["act_slug"]: row for row in active}

    ordered_slugs = [slug for slug in EXECUTION_ORDER if slug in by_slug]
    remaining_slugs = sorted(set(by_slug.keys()) - set(ordered_slugs))
    ordered_slugs.extend(remaining_slugs)

    summary_rows = []
    failed_parse = []
    total_chunks = 0
    mapped_populated = 0
    by_tier = defaultdict(int)
    by_source_type = defaultdict(int)
    by_act: dict[str, dict[str, Any]] = {}
    superseded_acts = []

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    for slug in ordered_slugs:
        entry = by_slug[slug]
        chunks, parse_error = chunk_entry(entry)

        if parse_error:
            failed_parse.append({"act_slug": slug, "reason": parse_error})
            summary_rows.append(
                {
                    "act_slug": slug,
                    "chunk_count": 0,
                    "avg_tokens": 0,
                    "parse_status": f"failed ({parse_error})",
                }
            )
            continue

        jsonl_path = CHUNKS_DIR / f"{slug}.jsonl"
        write_jsonl(jsonl_path, chunks)

        chunk_count = len(chunks)
        avg_tokens = (
            int(round(sum(c["token_estimate"] for c in chunks) / chunk_count))
            if chunk_count
            else 0
        )
        summary_rows.append(
            {
                "act_slug": slug,
                "chunk_count": chunk_count,
                "avg_tokens": avg_tokens,
                "parse_status": "ok",
            }
        )

        total_chunks += chunk_count
        tier_key = str(entry.get("tier") if entry.get("tier") is not None else 0)
        by_tier[tier_key] += chunk_count
        for chunk in chunks:
            by_source_type[chunk["source_type"]] += 1
            if chunk.get("mapped_to"):
                mapped_populated += 1

        if entry.get("is_superseded"):
            superseded_acts.append(slug)

        by_act[slug] = {
            "chunk_count": chunk_count,
            "is_superseded": bool(entry.get("is_superseded", False)),
            "jsonl_path": str(jsonl_path).replace("\\", "/"),
        }

    index = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_chunks": total_chunks,
        "by_tier": {
            "0": by_tier["0"],
            "1": by_tier["1"],
            "2": by_tier["2"],
            "3": by_tier["3"],
        },
        "by_source_type": dict(
            sorted(by_source_type.items(), key=lambda item: item[0])
        ),
        "by_act": by_act,
        "superseded_acts": sorted(set(superseded_acts)),
        "failed_parse": failed_parse,
    }

    index_path = CHUNKS_DIR / "index.json"
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    # CLI output requested by user.
    print("Act | Chunks Generated | Avg Token Estimate | Parse Status")
    for row in summary_rows:
        print(
            f"{row['act_slug']} | {row['chunk_count']} | {row['avg_tokens']} | {row['parse_status']}"
        )
    print(f"TOTAL_CHUNKS: {total_chunks}")
    print(f"MAPPED_TO_POPULATED_COUNT: {mapped_populated}")
    print(f"INDEX_WRITTEN: {index_path}")
    if failed_parse:
        print("FAILED_PARSE_ENTRIES:")
        for item in failed_parse:
            print(f"- {item['act_slug']}: {item['reason']}")
    else:
        print("FAILED_PARSE_ENTRIES: none")


if __name__ == "__main__":
    main()
