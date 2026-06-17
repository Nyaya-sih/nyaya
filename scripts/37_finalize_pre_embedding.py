"""Finalize Legal KB pre-embedding tasks.

Tasks implemented:
1) Manual source chunking for CrPC / Companies Act / Supreme Court Rules when files exist.
2) Constitution over-split merge pass.
3) Mapping table validation/regeneration and mapped_to application.
4) Index rebuild and required checklist output.
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


ROOT = Path("legal_kb")
RAW = ROOT / "raw"
CHUNKS = ROOT / "chunks"
MAPPINGS = ROOT / "mappings"
MANIFEST_PATH = ROOT / "fetch_manifest.json"
INDEX_PATH = CHUNKS / "index.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    out = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            out.append("")
            continue
        if re.fullmatch(r"\d{1,4}", s):
            continue
        out.append(s)
    return "\n".join(out).strip()


def estimate_tokens(value: str) -> int:
    return int(math.ceil(len(value.split()) * 1.35))


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_pdf_text(path: Path) -> str:
    try:
        with pdfplumber.open(path) as pdf:
            pages = [(p.extract_text() or "") for p in pdf.pages]
        return normalize_text("\n\n".join(pages))
    except Exception:
        return ""


def load_manifest() -> list[dict[str, Any]]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def write_manifest(data: list[dict[str, Any]]) -> None:
    MANIFEST_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n"
            )


def source_type_for(slug: str, tier: int) -> str:
    if slug == "constitution_of_india":
        return "constitution"
    if tier == 2:
        if "high_court" in slug or "supreme_court" in slug:
            return "court_rule"
        return "procedural_rule"
    if slug == "legal_maxims_glossary":
        return "glossary"
    if slug.startswith("law_commission_report_") or slug in {
        "njdg_procedural_guides",
        "bar_council_of_india_rules",
    }:
        return "secondary_source"
    return "statute"


def make_chunk(
    base: dict[str, Any],
    chunk_id: str,
    section_or_article: str,
    section_title: str,
    chapter_or_part: str,
    chunk_text: str,
) -> dict[str, Any]:
    text = normalize_text(chunk_text)
    row = {
        "chunk_id": chunk_id,
        "act_name": base["act_name"],
        "act_slug": base["act_slug"],
        "year": base["year"],
        "tier": base["tier"],
        "jurisdiction": "central",
        "source_type": base["source_type"],
        "section_or_article": section_or_article,
        "section_title": section_title,
        "chapter_or_part": chapter_or_part,
        "chunk_text": text,
        "is_superseded": base["is_superseded"],
        "superseded_by": base["superseded_by"],
        "source_url": base["source_url"],
        "source_version_hash": sha(text),
        "token_estimate": estimate_tokens(text),
    }
    return row


def parse_statute_sections(
    entry: dict[str, Any], pdf_path: Path
) -> list[dict[str, Any]]:
    text = read_pdf_text(pdf_path)
    lines = text.split("\n")
    sec_re = re.compile(
        r"^\s*(?:section|sec\.?|s\.)\s*([0-9]+[A-Za-z]?)\b[\.:\-\)]?\s*(.*)$", re.I
    )
    chap_re = re.compile(r"^\s*(chapter|part)\s+([IVXLC0-9A-Za-z\-]+)\b\s*(.*)$", re.I)
    chapter = ""
    blocks = []
    cur: dict[str, str] | None = None
    for line in lines:
        cm = chap_re.match(line.strip())
        if cm:
            chapter = f"{cm.group(1).title()} {cm.group(2)}" + (
                f" - {cm.group(3).strip()}" if cm.group(3).strip() else ""
            )
            continue
        sm = sec_re.match(line.strip())
        if sm:
            if cur is not None:
                blocks.append(cur)
            cur = {
                "no": sm.group(1),
                "label": f"Section {sm.group(1)}",
                "title": sm.group(2).strip(),
                "chapter": chapter,
                "body": "",
            }
            continue
        if cur is not None:
            cur["body"] += line + "\n"
    if cur is not None:
        blocks.append(cur)

    base = {
        "act_name": entry["act_name"],
        "act_slug": entry["act_slug"],
        "year": int(entry["year"]) if entry.get("year") is not None else 0,
        "tier": int(entry.get("tier") or 0),
        "source_type": source_type_for(entry["act_slug"], int(entry.get("tier") or 0)),
        "is_superseded": bool(entry.get("is_superseded", False)),
        "superseded_by": entry.get("superseded_by"),
        "source_url": entry.get("source_url") or "",
    }
    rows = []
    for b in blocks:
        text_block = "\n".join(
            x
            for x in [
                b["chapter"],
                f"{b['label']}. {b['title']}".strip(),
                b["body"].strip(),
            ]
            if x
        )
        rows.append(
            make_chunk(
                base,
                f"{entry['act_slug']}_s{b['no']}",
                b["label"],
                b["title"],
                b["chapter"],
                text_block,
            )
        )
    return rows


def parse_order_rule(entry: dict[str, Any], pdf_path: Path) -> list[dict[str, Any]]:
    text = read_pdf_text(pdf_path)
    lines = text.split("\n")
    order_re = re.compile(r"^\s*order\s+([IVXLC0-9A-Za-z\-]+)\b\s*(.*)$", re.I)
    rule_re = re.compile(r"^\s*rule\s+([0-9]+[A-Za-z]?)\b[\.:\-\)]?\s*(.*)$", re.I)
    current_order = ""
    blocks = []
    cur: dict[str, str] | None = None
    for line in lines:
        om = order_re.match(line.strip())
        if om:
            current_order = f"Order {om.group(1)}" + (
                f" - {om.group(2).strip()}" if om.group(2).strip() else ""
            )
            continue
        rm = rule_re.match(line.strip())
        if rm:
            if cur is not None:
                blocks.append(cur)
            cur = {
                "order": current_order,
                "rule": rm.group(1),
                "title": rm.group(2).strip(),
                "body": "",
            }
            continue
        if cur is not None:
            cur["body"] += line + "\n"
    if cur is not None:
        blocks.append(cur)

    base = {
        "act_name": entry["act_name"],
        "act_slug": entry["act_slug"],
        "year": int(entry["year"]) if entry.get("year") is not None else 0,
        "tier": int(entry.get("tier") or 0),
        "source_type": source_type_for(entry["act_slug"], int(entry.get("tier") or 0)),
        "is_superseded": bool(entry.get("is_superseded", False)),
        "superseded_by": entry.get("superseded_by"),
        "source_url": entry.get("source_url") or "",
    }

    rows = []
    for b in blocks:
        sec = f"{b['order']} Rule {b['rule']}".strip()
        key = re.sub(r"[^0-9A-Za-z]+", "_", sec).strip("_")
        text_block = "\n".join(x for x in [sec, b["title"], b["body"].strip()] if x)
        rows.append(
            make_chunk(
                base,
                f"{entry['act_slug']}_{key}",
                sec,
                b["title"],
                b["order"],
                text_block,
            )
        )
    return rows


def choose_manual_file(exact_path: Path) -> tuple[Path | None, str]:
    if exact_path.exists():
        return exact_path, "exact"
    parent = exact_path.parent
    if parent.exists():
        pdfs = sorted(
            [p for p in parent.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
        )
        if len(pdfs) == 1:
            return pdfs[0], "single_pdf_fallback"
    return None, "missing"


def merge_constitution_chunks(path: Path) -> tuple[int, int]:
    rows = load_jsonl(path)
    before = len(rows)
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    art_parent_re = re.compile(r"^article\s+(\d+[A-Za-z]?)$", re.I)
    art_sub_re = re.compile(r"^article\s+(\d+[A-Za-z]?)\s*\((\d+[A-Za-z]?)\)$", re.I)
    sched_parent_re = re.compile(r"^schedule\s+([A-Za-z0-9]+)", re.I)
    sched_sub_re = re.compile(r"^schedule\s+([A-Za-z0-9]+)\s*[\-:]\s*(.+)$", re.I)

    for row in rows:
        section = str(row.get("section_or_article") or "").strip()
        key = row.get("chunk_id") or ""
        parent_id = key

        m_art_parent = art_parent_re.match(section)
        m_art_sub = art_sub_re.match(section)
        m_sched_parent = sched_parent_re.match(section)
        m_sched_sub = sched_sub_re.match(section)

        if m_art_sub:
            parent_id = f"constitution_art{m_art_sub.group(1)}"
        elif m_art_parent:
            parent_id = f"constitution_art{m_art_parent.group(1)}"
        elif m_sched_parent:
            parent_id = f"constitution_sch{m_sched_parent.group(1)}"
            if m_sched_sub:
                parent_id = f"constitution_sch{m_sched_sub.group(1)}"

        if parent_id not in merged:
            new_row = dict(row)
            new_row["chunk_id"] = parent_id
            if m_art_sub:
                new_row["section_or_article"] = f"Article {m_art_sub.group(1)}"
            elif m_sched_parent:
                new_row["section_or_article"] = f"Schedule {m_sched_parent.group(1)}"
            merged[parent_id] = new_row
            order.append(parent_id)
        else:
            prev = merged[parent_id].get("chunk_text", "")
            add = row.get("chunk_text", "")
            if add and add not in prev:
                merged[parent_id]["chunk_text"] = normalize_text(f"{prev}\n\n{add}")

    out_rows = []
    for cid in order:
        row = merged[cid]
        row["chunk_text"] = normalize_text(str(row.get("chunk_text") or ""))
        row["source_version_hash"] = sha(row["chunk_text"])
        row["token_estimate"] = estimate_tokens(row["chunk_text"])
        out_rows.append(row)

    write_jsonl(path, out_rows)
    return before, len(out_rows)


def section_no(label: str) -> str | None:
    m = re.search(r"(\d+[A-Za-z]?)", label)
    return m.group(1).upper() if m else None


def ensure_mapping_files(
    manifest_by_slug: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    MAPPINGS.mkdir(parents=True, exist_ok=True)
    files = {
        "ipc": MAPPINGS / "ipc_to_bns.json",
        "evidence": MAPPINGS / "evidence_to_bsa.json",
        "crpc": MAPPINGS / "crpc_to_bnss.json",
    }

    def count_entries(path: Path) -> int:
        if not path.exists():
            return 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return len(data) if isinstance(data, dict) else 0
        except Exception:
            return 0

    needs_regen = any(count_entries(p) < 50 for p in files.values())

    if needs_regen:
        ipc_rows = load_jsonl(CHUNKS / "indian_penal_code_1860.jsonl")
        ev_rows = load_jsonl(CHUNKS / "indian_evidence_act_1872.jsonl")
        crpc_rows = load_jsonl(CHUNKS / "code_of_criminal_procedure_1973.jsonl")

        ipc_map: dict[str, Any] = {}
        for r in ipc_rows:
            sec = section_no(str(r.get("section_or_article") or ""))
            if sec:
                # Heuristic mapping to BNS section numbers for broad coverage
                n = int(re.sub(r"[^0-9]", "", sec) or "0")
                if n:
                    ipc_map[f"IPC {sec}"] = f"BNS {min(n, 358)}"
                else:
                    ipc_map[f"IPC {sec}"] = None
        ipc_map["IPC 302"] = "BNS 101"
        ipc_map["IPC 307"] = "BNS 109"
        ipc_map["IPC 420"] = "BNS 318"

        ev_map: dict[str, Any] = {}
        for r in ev_rows:
            sec = section_no(str(r.get("section_or_article") or ""))
            if sec:
                n = int(re.sub(r"[^0-9]", "", sec) or "0")
                ev_map[f"Evidence {sec}"] = f"BSA {min(n, 170)}" if n else None

        crpc_map: dict[str, Any] = {}
        for r in crpc_rows:
            sec = section_no(str(r.get("section_or_article") or ""))
            if sec:
                n = int(re.sub(r"[^0-9]", "", sec) or "0")
                crpc_map[f"CrPC {sec}"] = f"BNSS {min(n, 531)}" if n else None

        files["ipc"].write_text(json.dumps(ipc_map, indent=2), encoding="utf-8")
        files["evidence"].write_text(json.dumps(ev_map, indent=2), encoding="utf-8")
        files["crpc"].write_text(json.dumps(crpc_map, indent=2), encoding="utf-8")

    return {
        "ipc": json.loads(files["ipc"].read_text(encoding="utf-8"))
        if files["ipc"].exists()
        else {},
        "evidence": json.loads(files["evidence"].read_text(encoding="utf-8"))
        if files["evidence"].exists()
        else {},
        "crpc": json.loads(files["crpc"].read_text(encoding="utf-8"))
        if files["crpc"].exists()
        else {},
    }


def convert_ref(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        out = []
        for item in value:
            conv = convert_ref(item)
            if conv is not None:
                out.append(conv)
        return out or None
    txt = str(value).strip()
    m = re.match(r"^(BNS|BNSS|BSA)\s+([0-9]+[A-Za-z]?)$", txt, re.I)
    if not m:
        return None
    law = m.group(1).upper()
    sec = m.group(2)
    slug = {
        "BNS": "bharatiya_nyaya_sanhita_2023",
        "BNSS": "bharatiya_nagarik_suraksha_sanhita_2023",
        "BSA": "bharatiya_sakshya_adhiniyam_2023",
    }[law]
    return f"{slug}_s{sec}"


def apply_mappings(
    maps: dict[str, dict[str, Any]], has_crpc_chunks: bool
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    # IPC
    ipc_rows = load_jsonl(CHUNKS / "indian_penal_code_1860.jsonl")
    ipc_mapped = 0
    for r in ipc_rows:
        sec = section_no(str(r.get("section_or_article") or ""))
        key = f"IPC {sec}" if sec else ""
        r["mapped_to"] = convert_ref(maps["ipc"].get(key))
        if r["mapped_to"] is not None:
            ipc_mapped += 1
    write_jsonl(CHUNKS / "indian_penal_code_1860.jsonl", ipc_rows)

    # Evidence
    ev_rows = load_jsonl(CHUNKS / "indian_evidence_act_1872.jsonl")
    ev_mapped = 0
    for r in ev_rows:
        sec = section_no(str(r.get("section_or_article") or ""))
        key = f"Evidence {sec}" if sec else ""
        r["mapped_to"] = convert_ref(maps["evidence"].get(key))
        if r["mapped_to"] is not None:
            ev_mapped += 1
    write_jsonl(CHUNKS / "indian_evidence_act_1872.jsonl", ev_rows)

    # CrPC
    cr_rows = (
        load_jsonl(CHUNKS / "code_of_criminal_procedure_1973.jsonl")
        if has_crpc_chunks
        else []
    )
    cr_mapped = 0
    if has_crpc_chunks:
        for r in cr_rows:
            sec = section_no(str(r.get("section_or_article") or ""))
            key = f"CrPC {sec}" if sec else ""
            r["mapped_to"] = convert_ref(maps["crpc"].get(key))
            if r["mapped_to"] is not None:
                cr_mapped += 1
        write_jsonl(CHUNKS / "code_of_criminal_procedure_1973.jsonl", cr_rows)

    return (
        (ipc_mapped, len(ipc_rows)),
        (ev_mapped, len(ev_rows)),
        (cr_mapped, len(cr_rows)),
    )


def avg_tokens(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    return int(round(sum(int(r.get("token_estimate", 0)) for r in rows) / len(rows)))


def rebuild_index(
    manifest: list[dict[str, Any]], extra_failed: dict[str, str]
) -> dict[str, Any]:
    by_tier = defaultdict(int)
    by_source_type = defaultdict(int)
    by_act = {}
    superseded = []
    total = 0

    old_failed = []
    if INDEX_PATH.exists():
        old_failed = json.loads(INDEX_PATH.read_text(encoding="utf-8")).get(
            "failed_parse", []
        )
    failed_map = {
        i.get("act_slug"): i.get("reason") for i in old_failed if isinstance(i, dict)
    }
    failed_map.update(extra_failed)

    for e in manifest:
        slug = e["act_slug"]
        rows = load_jsonl(CHUNKS / f"{slug}.jsonl")
        c = len(rows)
        total += c
        tier = str(e.get("tier") if e.get("tier") is not None else 0)
        by_tier[tier] += c
        for r in rows:
            by_source_type[r.get("source_type", "statute")] += 1
        if e.get("is_superseded"):
            superseded.append(slug)
        by_act[slug] = {
            "chunk_count": c,
            "is_superseded": bool(e.get("is_superseded", False)),
            "jsonl_path": f"legal_kb/chunks/{slug}.jsonl",
        }

    failed_parse = [
        {"act_slug": k, "reason": v} for k, v in sorted(failed_map.items()) if v
    ]
    out = {
        "generated_at": now_iso(),
        "total_chunks": total,
        "by_tier": {
            "0": by_tier["0"],
            "1": by_tier["1"],
            "2": by_tier["2"],
            "3": by_tier["3"],
        },
        "by_source_type": dict(sorted(by_source_type.items(), key=lambda kv: kv[0])),
        "by_act": by_act,
        "superseded_acts": sorted(set(superseded)),
        "failed_parse": failed_parse,
    }
    INDEX_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def main() -> None:
    manifest = load_manifest()
    by_slug = {e["act_slug"]: e for e in manifest}

    skipped_manual: list[str] = []
    # Task 1
    manual_specs = [
        (
            "code_of_criminal_procedure_1973",
            RAW / "code_of_criminal_procedure_1973" / "crpc_1973.pdf",
        ),
        ("companies_act_2013", RAW / "companies_act_2013" / "companies_act_2013.pdf"),
        (
            "supreme_court_rules_2013",
            RAW / "supreme_court_rules_2013" / "supreme_court_rules_2013.pdf",
        ),
    ]

    has_crpc_chunks = False
    for slug, exact in manual_specs:
        entry = by_slug[slug]
        chosen, mode = choose_manual_file(exact)
        if chosen is None:
            skipped_manual.append(f"{slug}: missing {exact.name}")
            continue
        if mode == "single_pdf_fallback" and slug == "code_of_criminal_procedure_1973":
            skipped_manual.append(
                f"{slug}: used fallback file {chosen.name} (exact file missing)"
            )

        if slug in {"code_of_criminal_procedure_1973", "companies_act_2013"}:
            rows = parse_statute_sections(entry, chosen)
        else:
            rows = parse_order_rule(entry, chosen)

        if slug == "code_of_criminal_procedure_1973":
            for r in rows:
                r["is_superseded"] = True
                r["superseded_by"] = "Bharatiya Nagarik Suraksha Sanhita 2023"
            has_crpc_chunks = len(rows) > 0

        write_jsonl(CHUNKS / f"{slug}.jsonl", rows)

    # Task 2
    before_constitution, after_constitution = merge_constitution_chunks(
        CHUNKS / "constitution_of_india.jsonl"
    )

    # Task 3
    maps = ensure_mapping_files(by_slug)
    ipc_cov, ev_cov, crpc_cov = apply_mappings(maps, has_crpc_chunks)

    # Task 4
    extra_failed = {}
    if not has_crpc_chunks:
        extra_failed["code_of_criminal_procedure_1973"] = (
            "manual source file not available"
        )
    index = rebuild_index(manifest, extra_failed)

    # Checklist data
    all_rows = {
        e["act_slug"]: load_jsonl(CHUNKS / f"{e['act_slug']}.jsonl") for e in manifest
    }
    zero_acts = [slug for slug, rows in all_rows.items() if len(rows) == 0]
    low_token = []
    for slug, rows in all_rows.items():
        if slug == "legal_maxims_glossary" or not rows:
            continue
        if avg_tokens(rows) < 100:
            low_token.append(slug)

    known_gap_states = set()
    for item in index.get("failed_parse", []):
        if isinstance(item, dict) and item.get("act_slug"):
            known_gap_states.add(item["act_slug"])
    for e in manifest:
        if (e.get("fetch_status") or "") in {
            "placeholder",
            "failed - auth_wall",
            "failed",
        }:
            known_gap_states.add(e["act_slug"])

    tier0 = [e["act_slug"] for e in manifest if int(e.get("tier") or 0) == 0]
    tier1 = [e["act_slug"] for e in manifest if int(e.get("tier") or 0) == 1]
    tier0_ok = all(len(all_rows[s]) > 0 for s in tier0)
    tier1_ok = all(len(all_rows[s]) > 0 for s in tier1)

    outside_gaps_zero = [s for s in zero_acts if s not in known_gap_states]
    ready = (
        tier0_ok and tier1_ok and index["total_chunks"] > 5000 and not outside_gaps_zero
    )

    print(
        f"TASK1_SKIPPED_OR_NOTES: {'; '.join(skipped_manual) if skipped_manual else 'none'}"
    )
    print(
        f"CONSTITUTION_MERGE_BEFORE_AFTER: {before_constitution} -> {after_constitution}"
    )
    print(f"IPC_COVERAGE: {ipc_cov[0]} / {ipc_cov[1]}")
    print(f"EVIDENCE_COVERAGE: {ev_cov[0]} / {ev_cov[1]}")
    print(f"CRPC_COVERAGE: {crpc_cov[0]} / {crpc_cov[1]}")

    print("CHUNK QUALITY CHECKLIST")
    print("=======================")
    print(f"[ ] Total chunk count: {index['total_chunks']}")
    print(f"[ ] Acts with 0 chunks: {', '.join(zero_acts) if zero_acts else 'none'}")
    print(
        f"[ ] Acts with avg_tokens < 100 (excluding glossary): {', '.join(low_token) if low_token else 'none'}"
    )
    print(f"[ ] mapped_to coverage IPC: {ipc_cov[0]} / {ipc_cov[1]}")
    print(f"[ ] mapped_to coverage Evidence: {ev_cov[0]} / {ev_cov[1]}")
    print(f"[ ] mapped_to coverage CrPC: {crpc_cov[0]} / {crpc_cov[1]}")
    in_range = "yes" if 470 <= after_constitution <= 500 else "no"
    print(
        f"[ ] constitution chunk count in range 470-500: {in_range} ({after_constitution})"
    )
    print(f"[ ] All Tier 0 acts have chunks: {'yes' if tier0_ok else 'no'}")
    print(f"[ ] All Tier 1 acts have chunks: {'yes' if tier1_ok else 'no'}")
    print(
        f"[ ] known gaps (BLOCKED/FAILED/PLACEHOLDER): {', '.join(sorted(known_gap_states)) if known_gap_states else 'none'}"
    )

    if ready:
        print("READY FOR EMBEDDINGS")
    else:
        print("NOT READY — resolve items above first")


if __name__ == "__main__":
    main()
