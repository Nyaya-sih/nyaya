"""Fix legal KB chunk quality issues and regenerate index.

This script addresses:
- under-chunked acts by reparsing from raw sources
- low-token anomalous chunk sets
- mapping table creation + mapped_to population
- OCR failure marking for scanned law commission reports
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qs

import pdfplumber
import PyPDF2
import requests


ROOT = Path("legal_kb")
MANIFEST_PATH = ROOT / "fetch_manifest.json"
CHUNKS_DIR = ROOT / "chunks"
MAPPINGS_DIR = ROOT / "mappings"


UNDER_CHUNKED_ACTS = {
    "constitution_of_india",
    "code_of_criminal_procedure_1973",
    "supreme_court_rules_2013",
    "bombay_high_court_rules",
    "cpc_bnss_procedural_mapping_notes",
    "criminal_rules_of_practice",
    "specific_relief_act_1963",
    "companies_act_2013",
}

LOW_TOKEN_ANOMALY_ACTS = {
    "indian_penal_code_1860",
    "motor_vehicles_act_1988",
    "indian_evidence_act_1872",
    "legal_maxims_glossary",
    "law_commission_report_248",
    "law_commission_report_262",
}

MODIFIED_ACTS = (
    UNDER_CHUNKED_ACTS
    | LOW_TOKEN_ANOMALY_ACTS
    | {
        "law_commission_report_47",
        "law_commission_report_69",
        "law_commission_report_152",
    }
)


@dataclass
class ActFixResult:
    act_slug: str
    chunk_count: int
    avg_tokens: int
    parse_status: str


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    out_lines = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            out_lines.append("")
            continue
        if re.match(r"^\d{1,4}$", s):
            continue
        if re.search(
            r"download india code logo|content provided by the state government",
            s,
            re.I,
        ):
            continue
        out_lines.append(s)
    return "\n".join(out_lines).strip()


def strip_tags(value: str) -> str:
    value = re.sub(r"(?is)<script.*?>.*?</script>", " ", value)
    value = re.sub(r"(?is)<style.*?>.*?</style>", " ", value)
    value = re.sub(r"(?is)<[^>]+>", " ", value)
    value = html.unescape(value)
    return normalize_text(value)


def read_pdf_text(path: Path) -> str:
    text = ""
    try:
        with pdfplumber.open(path) as pdf:
            text = "\n\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception:
        pass

    if not text:
        try:
            with open(path, "rb") as handle:
                reader = PyPDF2.PdfReader(handle)
                text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            text = ""

    return normalize_text(text)


def read_source_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf_text(path)
    if suffix in {".html", ".htm"}:
        return strip_tags(path.read_text(encoding="utf-8", errors="ignore"))
    if suffix in {".md", ".txt"}:
        return normalize_text(path.read_text(encoding="utf-8", errors="ignore"))
    return ""


def estimate_tokens(value: str) -> int:
    return int(math.ceil(len(value.split()) * 1.35))


def source_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_type_for(slug: str, tier: int) -> str:
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
        if "high_court" in slug or "supreme_court" in slug:
            return "court_rule"
        return "procedural_rule"
    return "statute"


def jurisdiction_for(slug: str) -> str:
    if slug == "delhi_high_court_rules":
        return "state:delhi"
    if slug == "bombay_high_court_rules":
        return "state:maharashtra"
    if slug == "patna_high_court_rules":
        return "state:bihar"
    return "central"


def make_chunk(
    base: dict[str, Any],
    chunk_id: str,
    section_or_article: str,
    section_title: str,
    chapter_or_part: str,
    chunk_text: str,
) -> dict[str, Any]:
    text = normalize_text(chunk_text)
    record = {
        "chunk_id": chunk_id,
        "act_name": base["act_name"],
        "act_slug": base["act_slug"],
        "year": base["year"],
        "tier": base["tier"],
        "jurisdiction": base["jurisdiction"],
        "source_type": base["source_type"],
        "section_or_article": section_or_article,
        "section_title": section_title,
        "chapter_or_part": chapter_or_part,
        "chunk_text": text if text else f"{section_or_article} [Repealed]",
        "is_superseded": base["is_superseded"],
        "superseded_by": base["superseded_by"],
        "source_url": base["source_url"],
    }
    record["source_version_hash"] = source_hash(record["chunk_text"])
    record["token_estimate"] = estimate_tokens(record["chunk_text"])
    if not text:
        record["is_repealed"] = True
    return record


def base_from_manifest(entry: dict[str, Any]) -> dict[str, Any]:
    tier = int(entry.get("tier") or 0)
    slug = entry["act_slug"]
    return {
        "act_name": entry["act_name"],
        "act_slug": slug,
        "year": int(entry["year"]) if entry.get("year") is not None else 0,
        "tier": tier,
        "jurisdiction": jurisdiction_for(slug),
        "source_type": source_type_for(slug, tier),
        "is_superseded": bool(entry.get("is_superseded", False)),
        "superseded_by": entry.get("superseded_by"),
        "source_url": entry.get("source_url") or "",
    }


def parse_constitution(
    entry: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    path = Path(entry["file_path"])
    text = read_source_text(path)
    article_hits = re.findall(r"(?im)^\s*article\s+\d+[A-Za-z]?\b", text)
    if len(article_hits) < 50:
        return [], "source mismatch - constitution text unavailable in raw file"

    base = base_from_manifest(entry)
    blocks: list[dict[str, Any]] = []
    lines = text.split("\n")
    art_re = re.compile(r"^\s*article\s+([0-9]+[A-Za-z]?)\b[\.:\-\)]?\s*(.*)$", re.I)
    sch_re = re.compile(
        r"^\s*((?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|\d+(?:st|nd|rd|th))\s+schedule\b.*)$",
        re.I,
    )

    current: dict[str, Any] | None = None
    for line in lines:
        am = art_re.match(line.strip())
        sm = sch_re.match(line.strip())
        if am:
            if current is not None:
                blocks.append(current)
            current = {
                "kind": "art",
                "key": am.group(1),
                "label": f"Article {am.group(1)}",
                "title": am.group(2).strip(),
                "body": "",
            }
            continue
        if sm:
            if current is not None:
                blocks.append(current)
            label = sm.group(1).strip()
            key = re.sub(r"[^A-Za-z0-9]+", "", label.split()[0])
            current = {
                "kind": "sch",
                "key": key,
                "label": f"Schedule {label}",
                "title": label,
                "body": "",
            }
            continue
        if current is not None:
            current["body"] += line + "\n"
    if current is not None:
        blocks.append(current)

    chunks = []
    for b in blocks:
        cid = (
            f"constitution_art{b['key']}"
            if b["kind"] == "art"
            else f"constitution_sch{b['key']}"
        )
        chunks.append(
            make_chunk(
                base,
                cid,
                b["label"],
                b["title"],
                "",
                f"{b['label']}. {b['title']}\n{b['body']}",
            )
        )
    return chunks, None if chunks else "constitution parse produced no chunks"


def parse_statute_sections(
    text: str, slug: str, base: dict[str, Any]
) -> list[dict[str, Any]]:
    sec_re = re.compile(
        r"(?im)^\s*(?:section|sec\.?|s\.)\s*([0-9]+[A-Za-z]?)\b[\.:\-\)]?\s*(.*)$"
    )
    chapter_re = re.compile(
        r"(?im)^\s*(chapter|part)\s+([IVXLC0-9A-Za-z\-]+)\b\s*(.*)$"
    )

    lines = text.split("\n")
    chapter = ""
    blocks = []
    current = None

    for line in lines:
        cm = chapter_re.match(line.strip())
        if cm:
            chapter = f"{cm.group(1).title()} {cm.group(2)}" + (
                f" - {cm.group(3).strip()}" if cm.group(3).strip() else ""
            )
            continue

        sm = sec_re.match(line.strip())
        if sm:
            if current:
                blocks.append(current)
            current = {
                "sec_no": sm.group(1),
                "sec_label": f"Section {sm.group(1)}",
                "title": sm.group(2).strip(),
                "chapter": chapter,
                "body": "",
            }
            continue

        if current:
            current["body"] += line + "\n"

    if current:
        blocks.append(current)

    chunks = []
    for block in blocks:
        chunk_text = "\n".join(
            item
            for item in [
                block["chapter"],
                f"{block['sec_label']}. {block['title']}".strip(),
                block["body"].strip(),
            ]
            if item
        )
        chunks.append(
            make_chunk(
                base,
                f"{slug}_s{block['sec_no']}",
                block["sec_label"],
                block["title"],
                block["chapter"],
                chunk_text,
            )
        )
    return chunks


def parse_numbered_sections(
    text: str, slug: str, base: dict[str, Any]
) -> list[dict[str, Any]]:
    sec_re = re.compile(r"(?m)^\s*(\d+[A-Za-z]?)\.\s*(.*)$")
    lines = text.split("\n")
    matches = [
        (i, m.group(1), m.group(2).strip())
        for i, line in enumerate(lines)
        for m in [sec_re.match(line.strip())]
        if m
    ]
    if not matches:
        return []

    chunks = []
    for idx, (line_no, sec_no, title) in enumerate(matches):
        start = line_no + 1
        end = matches[idx + 1][0] if idx + 1 < len(matches) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        chunk_text = f"Section {sec_no}. {title}\n{body}".strip()
        chunks.append(
            make_chunk(
                base,
                f"{slug}_s{sec_no}",
                f"Section {sec_no}",
                title,
                "",
                chunk_text,
            )
        )
    return chunks


def extract_sections_from_indiacode_html(raw_html: str) -> list[dict[str, str]]:
    section_pattern = re.compile(
        r"<a[^>]+href\s*=\s*[\"']?/show-data\?([^\"'\s>]+)[^>]*>(.*?)</a>",
        re.I | re.S,
    )
    chapter_pattern = re.compile(r"<b>\s*(CHAPTER\s+[^<]+)</b>", re.I)

    sections = []
    seen: set[tuple[str, str]] = set()
    for m in section_pattern.finditer(raw_html):
        query = m.group(1).replace("&amp;", "&")
        query = query.replace("§ion", "section")
        inner_text = strip_tags(m.group(2))
        sec_match = re.search(r"\bSection\s*([0-9A-Za-z]+)\.", inner_text, re.I)
        sec_no = sec_match.group(1).strip() if sec_match else ""
        if not sec_no:
            params = parse_qs(query)
            sec_no = ((params.get("sectionno") or [""])[0] or "").strip()
        if not sec_no:
            continue

        sec_title = re.sub(
            rf"^\s*Section\s*{re.escape(sec_no)}\.\s*",
            "",
            inner_text,
            flags=re.I,
        ).strip()
        start = m.start()
        prefix = raw_html[max(0, start - 2000) : start]
        chapter_matches = chapter_pattern.findall(prefix)
        chapter = strip_tags(chapter_matches[-1]) if chapter_matches else ""

        dedupe_key = (sec_no, query)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        sections.append(
            {
                "query": query,
                "sec_no": sec_no,
                "sec_title": sec_title,
                "chapter": chapter,
            }
        )
    return sections


def fetch_section_body(session: requests.Session, query: str) -> str:
    params = parse_qs(query)
    actid = (params.get("actid") or [None])[0]
    section_id = (params.get("sectionId") or params.get("sectionID") or [None])[0]
    if not actid or not section_id:
        return ""

    show_url = f"https://www.indiacode.nic.in/show-data?{query}"
    try:
        session.get(show_url, timeout=40)
    except Exception:
        pass

    try:
        resp = session.get(
            "https://www.indiacode.nic.in/SectionPageContent",
            params={"actid": actid, "sectionID": section_id},
            timeout=40,
            headers={
                "Referer": show_url,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
        )
        if resp.status_code != 200:
            return ""
        payload = resp.json()
    except Exception:
        return ""

    content = strip_tags(str(payload.get("content", "")))
    footnote = strip_tags(str(payload.get("footnote", "")))
    if footnote:
        content = (content + "\n\n" + footnote).strip()
    return content


def parse_indiacode_fallback(
    entry: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    path = Path(entry["file_path"])
    raw_html = path.read_text(encoding="utf-8", errors="ignore")
    sections = extract_sections_from_indiacode_html(raw_html)
    if not sections:
        return [], "no section anchors in IndiaCode fallback html"

    base = base_from_manifest(entry)
    slug = entry["act_slug"]
    sess = requests.Session()
    sess.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    chunks = []
    for sec in sections:
        body = fetch_section_body(sess, sec["query"])
        chunk_text = "\n".join(
            item
            for item in [
                sec["chapter"],
                f"Section {sec['sec_no']}. {sec['sec_title']}".strip(),
                body,
            ]
            if item
        )
        chunks.append(
            make_chunk(
                base,
                f"{slug}_s{sec['sec_no']}",
                f"Section {sec['sec_no']}",
                sec["sec_title"],
                sec["chapter"],
                chunk_text,
            )
        )
    return chunks, None


def parse_law_commission_coarse(
    entry: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    text = read_source_text(Path(entry["file_path"]))
    if not text:
        return [], "scanned PDF - OCR failed"

    lines = text.split("\n")
    heading_re = re.compile(
        r"^\s*(CHAPTER\s+[IVXLC0-9]+.*|\d+\.\s+[A-Z][A-Za-z][^\n]{4,})$", re.I
    )
    blocks = []
    current = None
    for line in lines:
        s = line.strip()
        hm = heading_re.match(s)
        if hm and len(s) < 180:
            if current is not None:
                blocks.append(current)
            current = {"heading": s, "body": ""}
            continue
        if current is not None:
            current["body"] += line + "\n"
    if current is not None:
        blocks.append(current)

    if len(blocks) < 5:
        # fallback to larger paragraph windows
        words = text.split()
        blocks = []
        step = 350
        for i in range(0, len(words), step):
            chunk_words = words[i : i + step]
            if not chunk_words:
                continue
            blocks.append(
                {"heading": f"Section {len(blocks) + 1}", "body": " ".join(chunk_words)}
            )

    base = base_from_manifest(entry)
    report_no = entry["act_slug"].split("_")[-1]
    chunks = []
    for idx, block in enumerate(blocks, start=1):
        label = re.sub(r"\s+", " ", block["heading"]).strip()
        key = re.sub(r"[^0-9A-Za-z]+", "_", label).strip("_") or str(idx)
        chunk_text = f"{label}\n{block['body']}"
        chunks.append(
            make_chunk(
                base,
                f"lcr_{report_no}_s{key}",
                f"Section {label}",
                label,
                "",
                chunk_text,
            )
        )
    return chunks, None


def parse_glossary(entry: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    text = read_source_text(Path(entry["file_path"]))
    base = base_from_manifest(entry)
    pattern = re.compile(
        r"^\s*(\d+)\.\s*\*\*(.+?)\*\*\s*-\s*(.+?)\s*-\s*Example:\s*(.+?)$", re.M
    )
    chunks = []
    for m in pattern.finditer(text):
        idx = int(m.group(1))
        maxim = m.group(2).strip()
        meaning = m.group(3).strip()
        usage = m.group(4).strip()
        chunk_text = f"{maxim}\nMeaning: {meaning}\nUsage: {usage}"
        chunks.append(
            make_chunk(
                base,
                f"glossary_maxim_{idx:03d}",
                maxim,
                maxim,
                "",
                chunk_text,
            )
        )
    return chunks, None if chunks else "no glossary entries parsed"


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n"
            )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sec_no_from_chunk(chunk: dict[str, Any]) -> str | None:
    label = str(chunk.get("section_or_article") or "")
    m = re.search(r"(\d+[A-Za-z]?)", label)
    return m.group(1).upper() if m else None


def write_mapping_files(
    manifest_entries: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)

    ipc_rows = load_jsonl(CHUNKS_DIR / "indian_penal_code_1860.jsonl")
    crpc_rows = load_jsonl(CHUNKS_DIR / "code_of_criminal_procedure_1973.jsonl")
    ev_rows = load_jsonl(CHUNKS_DIR / "indian_evidence_act_1872.jsonl")

    ipc_map: dict[str, Any] = {}
    for row in ipc_rows:
        sec = sec_no_from_chunk(row)
        if sec:
            ipc_map[f"IPC {sec}"] = None
    # Only known explicit mappings supplied with confidence.
    ipc_map["IPC 302"] = "BNS 101"
    ipc_map["IPC 307"] = "BNS 109"

    crpc_map: dict[str, Any] = {}
    for row in crpc_rows:
        sec = sec_no_from_chunk(row)
        if sec:
            crpc_map[f"CrPC {sec}"] = None

    evidence_map: dict[str, Any] = {}
    for row in ev_rows:
        sec = sec_no_from_chunk(row)
        if sec:
            evidence_map[f"Evidence {sec}"] = None

    (MAPPINGS_DIR / "ipc_to_bns.json").write_text(
        json.dumps(ipc_map, indent=2), encoding="utf-8"
    )
    (MAPPINGS_DIR / "crpc_to_bnss.json").write_text(
        json.dumps(crpc_map, indent=2), encoding="utf-8"
    )
    (MAPPINGS_DIR / "evidence_to_bsa.json").write_text(
        json.dumps(evidence_map, indent=2), encoding="utf-8"
    )

    return ipc_map, crpc_map, evidence_map


def convert_mapping_to_chunk_ref(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        converted = [convert_mapping_to_chunk_ref(item) for item in value]
        return converted
    text = str(value).strip()
    m = re.match(r"^(BNS|BNSS|BSA)\s+([0-9]+[A-Za-z]?)$", text, re.I)
    if not m:
        return None
    law = m.group(1).upper()
    sec = m.group(2)
    slug_map = {
        "BNS": "bharatiya_nyaya_sanhita_2023",
        "BNSS": "bharatiya_nagarik_suraksha_sanhita_2023",
        "BSA": "bharatiya_sakshya_adhiniyam_2023",
    }
    return f"{slug_map[law]}_s{sec}"


def apply_mappings_to_chunks(
    ipc_map: dict[str, Any], crpc_map: dict[str, Any], evidence_map: dict[str, Any]
) -> dict[str, tuple[int, int]]:
    coverage: dict[str, tuple[int, int]] = {}

    specs = [
        ("indian_penal_code_1860", "IPC", ipc_map),
        ("code_of_criminal_procedure_1973", "CrPC", crpc_map),
        ("indian_evidence_act_1872", "Evidence", evidence_map),
    ]

    for slug, prefix, mapping in specs:
        path = CHUNKS_DIR / f"{slug}.jsonl"
        rows = load_jsonl(path)
        mapped_count = 0
        for row in rows:
            sec = sec_no_from_chunk(row)
            key = f"{prefix} {sec}" if sec else None
            mapped_value = mapping.get(key) if key else None
            converted = convert_mapping_to_chunk_ref(mapped_value)
            row["mapped_to"] = converted
            if converted is not None:
                mapped_count += 1
        write_jsonl(path, rows)
        coverage[slug] = (mapped_count, len(rows))

    return coverage


def regenerate_index(
    manifest_entries: list[dict[str, Any]], failed_parse: list[dict[str, str]]
) -> dict[str, Any]:
    by_tier = defaultdict(int)
    by_source_type = defaultdict(int)
    by_act: dict[str, dict[str, Any]] = {}
    superseded = []

    total = 0
    for entry in manifest_entries:
        slug = entry["act_slug"]
        jsonl_path = CHUNKS_DIR / f"{slug}.jsonl"
        rows = load_jsonl(jsonl_path)
        count = len(rows)
        total += count
        tier = str(entry.get("tier") if entry.get("tier") is not None else 0)
        by_tier[tier] += count
        for row in rows:
            by_source_type[row.get("source_type", "statute")] += 1
        if entry.get("is_superseded"):
            superseded.append(slug)

        by_act[slug] = {
            "chunk_count": count,
            "is_superseded": bool(entry.get("is_superseded", False)),
            "jsonl_path": str(jsonl_path).replace("\\", "/"),
        }

    index = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_chunks": total,
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
        "superseded_acts": sorted(set(superseded)),
        "failed_parse": failed_parse,
    }
    (CHUNKS_DIR / "index.json").write_text(
        json.dumps(index, indent=2), encoding="utf-8"
    )
    return index


def avg_tokens(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    return int(round(sum(int(r.get("token_estimate", 0)) for r in rows) / len(rows)))


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    active = [
        m for m in manifest if m.get("fetch_status") in {"success", "fallback_used"}
    ]
    by_slug = {m["act_slug"]: m for m in active}

    fix_results: list[ActFixResult] = []
    failed_parse: list[dict[str, str]] = []

    # Required diagnostic print: first 10 chunk_text values for anomaly acts.
    print("ANOMALY_DIAGNOSTICS_START")
    for slug in [
        "indian_penal_code_1860",
        "motor_vehicles_act_1988",
        "indian_evidence_act_1872",
        "legal_maxims_glossary",
        "law_commission_report_248",
        "law_commission_report_262",
    ]:
        rows = load_jsonl(CHUNKS_DIR / f"{slug}.jsonl")
        print(f"{slug}: first_10_chunk_text")
        for row in rows[:10]:
            print(f"- {row.get('chunk_id')}: {row.get('chunk_text', '')[:300]}")
    print("ANOMALY_DIAGNOSTICS_END")

    for slug in sorted(MODIFIED_ACTS):
        entry = by_slug.get(slug)
        if entry is None:
            continue

        chunks: list[dict[str, Any]] = []
        parse_error: str | None = None

        if slug == "constitution_of_india":
            chunks, parse_error = parse_constitution(entry)
        elif slug in {
            "indian_penal_code_1860",
            "code_of_criminal_procedure_1973",
            "indian_evidence_act_1872",
            "motor_vehicles_act_1988",
        }:
            chunks, parse_error = parse_indiacode_fallback(entry)
        elif slug in {
            "law_commission_report_248",
            "law_commission_report_262",
            "law_commission_report_47",
            "law_commission_report_69",
            "law_commission_report_152",
        }:
            chunks, parse_error = parse_law_commission_coarse(entry)
        elif slug == "legal_maxims_glossary":
            chunks, parse_error = parse_glossary(entry)
        elif slug == "specific_relief_act_1963":
            text = read_source_text(Path(entry["file_path"]))
            base = base_from_manifest(entry)
            chunks = parse_numbered_sections(text, slug, base)
            if not chunks:
                parse_error = "unable to parse numbered sections from source"
        elif slug in {
            "supreme_court_rules_2013",
            "companies_act_2013",
            "criminal_rules_of_practice",
            "cpc_bnss_procedural_mapping_notes",
            "bombay_high_court_rules",
        }:
            parse_error = (
                "source mismatch - fetched raw file is not target legal instrument"
            )
        else:
            parse_error = "no remediation rule implemented"

        out_path = CHUNKS_DIR / f"{slug}.jsonl"
        if parse_error:
            if out_path.exists():
                out_path.unlink()
            failed_parse.append({"act_slug": slug, "reason": parse_error})
            fix_results.append(ActFixResult(slug, 0, 0, f"failed ({parse_error})"))
            continue

        write_jsonl(out_path, chunks)
        fix_results.append(ActFixResult(slug, len(chunks), avg_tokens(chunks), "ok"))

    # Mapping tables and mapped_to population.
    ipc_map, crpc_map, evidence_map = write_mapping_files(by_slug)
    coverage = apply_mappings_to_chunks(ipc_map, crpc_map, evidence_map)

    # Merge with non-remediated historical failures if still unresolved.
    existing_index_path = CHUNKS_DIR / "index.json"
    if existing_index_path.exists():
        old_failed = json.loads(existing_index_path.read_text(encoding="utf-8")).get(
            "failed_parse", []
        )
    else:
        old_failed = []
    old_failed_by_slug = {
        item.get("act_slug"): item for item in old_failed if isinstance(item, dict)
    }
    for slug in {
        "law_commission_report_47",
        "law_commission_report_69",
        "law_commission_report_152",
    }:
        if not any(item["act_slug"] == slug for item in failed_parse):
            old = old_failed_by_slug.get(slug)
            if old:
                failed_parse.append(old)

    index = regenerate_index(active, failed_parse)

    # Report post-fix token averages for issue-2 acts.
    print("POST_FIX_AVG_TOKENS_START")
    for slug in [
        "indian_penal_code_1860",
        "motor_vehicles_act_1988",
        "indian_evidence_act_1872",
        "legal_maxims_glossary",
        "law_commission_report_248",
        "law_commission_report_262",
    ]:
        rows = load_jsonl(CHUNKS_DIR / f"{slug}.jsonl")
        print(f"{slug}: count={len(rows)} avg_tokens={avg_tokens(rows)}")
    print("POST_FIX_AVG_TOKENS_END")

    print("UPDATED_CHUNK_COUNTS_START")
    for item in fix_results:
        print(
            f"{item.act_slug} | {item.chunk_count} | {item.avg_tokens} | {item.parse_status}"
        )
    print("UPDATED_CHUNK_COUNTS_END")

    ipc_cov = coverage.get("indian_penal_code_1860", (0, 0))
    crpc_cov = coverage.get("code_of_criminal_procedure_1973", (0, 0))
    ev_cov = coverage.get("indian_evidence_act_1872", (0, 0))
    print(f"MAPPING_COVERAGE IPC: {ipc_cov[0]} / {ipc_cov[1]}")
    print(f"MAPPING_COVERAGE CRPC: {crpc_cov[0]} / {crpc_cov[1]}")
    print(f"MAPPING_COVERAGE EVIDENCE: {ev_cov[0]} / {ev_cov[1]}")

    print(f"NEW_TOTAL_CHUNKS: {index['total_chunks']}")
    print("FAILED_PARSE_START")
    if not failed_parse:
        print("none")
    else:
        for item in failed_parse:
            print(f"{item['act_slug']}: {item['reason']}")
    print("FAILED_PARSE_END")

    # Acts still below token threshold for manual review.
    low_token_flags = []
    for slug, act_meta in index["by_act"].items():
        rows = load_jsonl(CHUNKS_DIR / f"{slug}.jsonl")
        if rows and avg_tokens(rows) < 100:
            low_token_flags.append((slug, avg_tokens(rows), len(rows)))

    print("LOW_TOKEN_MANUAL_REVIEW_START")
    if not low_token_flags:
        print("none")
    else:
        for slug, avg, count in sorted(low_token_flags, key=lambda item: item[0]):
            print(f"{slug}: avg_tokens={avg}, chunk_count={count}")
    print("LOW_TOKEN_MANUAL_REVIEW_END")


if __name__ == "__main__":
    main()
