"""Targeted re-fetch + re-chunk for blocked legal KB documents.

Steps:
1) Re-fetch only selected mismatched sources and update fetch_manifest.json.
2) Re-chunk only successfully refreshed/generated targets.
3) Regenerate chunks/index.json and print final status table.
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
import requests


ROOT = Path("legal_kb")
RAW = ROOT / "raw"
CHUNKS = ROOT / "chunks"
MANIFEST = ROOT / "fetch_manifest.json"
INDEX = CHUNKS / "index.json"
MAPPINGS = ROOT / "mappings"


TARGET_SLUGS = {
    "constitution_of_india",
    "companies_act_2013",
    "supreme_court_rules_2013",
    "code_of_criminal_procedure_1973",
    "criminal_rules_of_practice",
    "bombay_high_court_rules",
    "cpc_bnss_procedural_mapping_notes",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    lines: list[str] = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            lines.append("")
            continue
        if re.fullmatch(r"\d{1,4}", s):
            continue
        lines.append(s)
    return "\n".join(lines).strip()


def estimate_tokens(text: str) -> int:
    return int(math.ceil(len(text.split()) * 1.35))


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_pdf_text(path: Path) -> str:
    try:
        with pdfplumber.open(path) as pdf:
            pages = [(page.extract_text() or "") for page in pdf.pages]
        return normalize_text("\n\n".join(pages))
    except Exception:
        return ""


def read_md_text(path: Path) -> str:
    return normalize_text(path.read_text(encoding="utf-8", errors="ignore"))


def read_html_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    raw = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style.*?>.*?</style>", " ", raw)
    raw = re.sub(r"(?is)<[^>]+>", "\n", raw)
    return normalize_text(raw)


def load_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf_text(path)
    if suffix in {".md", ".txt"}:
        return read_md_text(path)
    if suffix in {".html", ".htm"}:
        return read_html_text(path)
    return ""


def source_type_for(slug: str, tier: int) -> str:
    if slug == "constitution_of_india":
        return "constitution"
    if tier == 2:
        if "high_court" in slug or "supreme_court" in slug:
            return "court_rule"
        return "procedural_rule"
    return "statute"


def jurisdiction_for(slug: str) -> str:
    if slug == "bombay_high_court_rules":
        return "state:maharashtra"
    return "central"


def make_base(entry: dict[str, Any]) -> dict[str, Any]:
    tier = int(entry.get("tier") or 0)
    return {
        "act_name": entry["act_name"],
        "act_slug": entry["act_slug"],
        "year": int(entry["year"]) if entry.get("year") is not None else 0,
        "tier": tier,
        "jurisdiction": jurisdiction_for(entry["act_slug"]),
        "source_type": source_type_for(entry["act_slug"], tier),
        "is_superseded": bool(entry.get("is_superseded", False)),
        "superseded_by": entry.get("superseded_by"),
        "source_url": entry.get("source_url") or "",
    }


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
        "jurisdiction": base["jurisdiction"],
        "source_type": base["source_type"],
        "section_or_article": section_or_article,
        "section_title": section_title,
        "chapter_or_part": chapter_or_part,
        "chunk_text": text,
        "is_superseded": base["is_superseded"],
        "superseded_by": base["superseded_by"],
        "source_url": base["source_url"],
        "source_version_hash": source_hash(text),
        "token_estimate": estimate_tokens(text),
    }
    return row


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
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def avg_tokens(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    return int(round(sum(int(r.get("token_estimate", 0)) for r in rows) / len(rows)))


def fetch_url(url: str, timeout: int = 50) -> tuple[int, bytes, str]:
    resp = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0"},
        allow_redirects=True,
    )
    ctype = (resp.headers.get("Content-Type") or "").lower()
    return resp.status_code, resp.content, ctype


def extract_first_pdf_link(html: str, base: str) -> str | None:
    for pat in [
        r'href\s*=\s*"([^"]+?\.pdf(?:\?[^\"]*)?)"',
        r"href\s*=\s*'([^']+?\.pdf(?:\?[^']*)?)'",
        r'href\s*=\s*"([^"]*?/bitstream/[^"]+)"',
    ]:
        m = re.search(pat, html, re.I)
        if m:
            link = m.group(1)
            if link.startswith("http://") or link.startswith("https://"):
                return link
            if link.startswith("/"):
                return "https://www.indiacode.nic.in" + link
            return base.rstrip("/") + "/" + link
    return None


def save_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def attempt_pdf_sources(
    entry: dict[str, Any],
    priorities: list[str],
    target_path: Path,
    validator,
) -> tuple[str, str, str | None]:
    for src in priorities:
        try:
            status, content, ctype = fetch_url(src)
            if status >= 400:
                continue
            data = content
            chosen_url = src
            if b"<html" in content[:500].lower() or "text/html" in ctype:
                html_text = content.decode("utf-8", errors="ignore")
                pdf_link = extract_first_pdf_link(html_text, src)
                if not pdf_link:
                    continue
                s2, c2, ctype2 = fetch_url(pdf_link)
                if s2 >= 400:
                    continue
                if b"<html" in c2[:500].lower() and "pdf" not in ctype2:
                    continue
                chosen_url = pdf_link
                data = c2
            save_bytes(target_path, data)
            text = read_pdf_text(target_path)
            if validator(text):
                return "success", chosen_url, None
        except Exception:
            continue
    return "failed", priorities[0], "all priority sources failed"


def strip_html(html_text: str) -> str:
    html_text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html_text)
    html_text = re.sub(r"(?is)<style.*?>.*?</style>", " ", html_text)
    html_text = re.sub(r"(?is)<[^>]+>", "\n", html_text)
    return normalize_text(html_text)


def scrape_constitutionofindia_to_markdown(dest: Path) -> int:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    root_map = session.get(
        "https://www.constitutionofindia.net/sitemap.xml", timeout=40
    )
    if root_map.status_code >= 400:
        return 0

    child_maps = re.findall(r"<loc>(.*?)</loc>", root_map.text)
    article_maps = [m for m in child_maps if "articles-sitemap" in m]
    schedule_maps = [m for m in child_maps if "schedules-sitemap" in m]
    if not article_maps:
        return 0

    article_urls: list[str] = []
    schedule_urls: list[str] = []
    for sm in article_maps + schedule_maps:
        try:
            xml = session.get(sm, timeout=40).text
            urls = re.findall(r"<loc>(.*?)</loc>", xml)
            if "articles-sitemap" in sm:
                article_urls.extend(urls)
            else:
                schedule_urls.extend(urls)
        except Exception:
            continue

    lines: list[str] = ["# Constitution of India (Scraped)"]
    article_count = 0
    for url in sorted(set(article_urls)):
        m = re.search(r"/articles/article-([0-9]+[a-z]?)", url, re.I)
        if not m:
            continue
        art_no = m.group(1).upper()
        try:
            resp = session.get(url, timeout=40)
            if resp.status_code >= 400:
                continue
            text = strip_html(resp.text)
            if len(text.split()) < 40:
                continue
            lines.append(f"\nArticle {art_no}")
            lines.append(text)
            article_count += 1
        except Exception:
            continue

    for url in sorted(set(schedule_urls)):
        m = re.search(r"/schedules/([a-z0-9\-]+)", url, re.I)
        sched = m.group(1).replace("-", " ").title() if m else "Schedule"
        try:
            resp = session.get(url, timeout=40)
            if resp.status_code >= 400:
                continue
            text = strip_html(resp.text)
            if len(text.split()) < 40:
                continue
            lines.append(f"\n{sched} Schedule")
            lines.append(text)
        except Exception:
            continue

    if article_count < 200:
        return 0

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines), encoding="utf-8")
    return article_count


def refetch_targets(manifest: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    by_slug = {m["act_slug"]: m for m in manifest}

    # constitution_of_india
    e = by_slug["constitution_of_india"]
    p = Path(e["file_path"])
    status, chosen, reason = attempt_pdf_sources(
        e,
        [
            "https://www.indiacode.nic.in/handle/123456789/15240",
            "https://legislative.gov.in/sites/default/files/COI-updated-as-31072018.pdf",
        ],
        p,
        lambda t: len(re.findall(r"(?im)^\s*article\s+\d+", t)) >= 300,
    )
    if status != "success":
        # priority 3: constitutionofindia.net article scrape fallback
        try:
            p = (
                RAW
                / "constitution_of_india"
                / "constitution_of_india_constitutionofindia_net.md"
            )
            scraped = scrape_constitutionofindia_to_markdown(p)
            if scraped >= 200:
                status, chosen, reason = (
                    "fallback_used",
                    "https://www.constitutionofindia.net",
                    f"article-by-article scrape completed ({scraped} articles)",
                )
                e["file_path"] = str(p).replace("\\", "/")
        except Exception:
            pass
    if status == "success":
        e["fallback_reason"] = None
    else:
        e["fallback_reason"] = reason
    e["source_url"] = chosen
    e["fetch_timestamp"] = now_iso()
    e["fetch_status"] = status
    e["file_size_bytes"] = (
        Path(e["file_path"]).stat().st_size if Path(e["file_path"]).exists() else 0
    )
    result[e["act_slug"]] = status

    # companies_act_2013
    e = by_slug["companies_act_2013"]
    p = Path(e["file_path"])
    status, chosen, reason = attempt_pdf_sources(
        e,
        [
            "https://www.indiacode.nic.in/handle/123456789/2171",
            "https://www.mca.gov.in/Ministry/pdf/CompaniesAct2013.pdf",
        ],
        p,
        lambda t: (
            len(re.findall(r"(?im)^\s*(?:section|sec\.?|s\.)\s*\d+", t)) >= 200
            or "companies act, 2013" in t.lower()
        ),
    )
    e["source_url"] = chosen
    e["fetch_timestamp"] = now_iso()
    e["fetch_status"] = status
    e["fallback_reason"] = None if status == "success" else reason
    e["file_size_bytes"] = p.stat().st_size if p.exists() else 0
    result[e["act_slug"]] = status

    # supreme_court_rules_2013
    e = by_slug["supreme_court_rules_2013"]
    p = Path(e["file_path"])
    status, chosen, reason = attempt_pdf_sources(
        e,
        [
            "https://main.sci.gov.in/pdf/Rules/SCI%20RULES%202013.pdf",
            "https://legislative.gov.in",
        ],
        p,
        lambda t: (
            "supreme court rules" in t.lower()
            and len(re.findall(r"(?im)^\s*order\s+[ivxlc0-9]+", t)) >= 20
        ),
    )
    e["source_url"] = chosen
    e["fetch_timestamp"] = now_iso()
    e["fetch_status"] = status
    e["fallback_reason"] = None if status == "success" else reason
    e["file_size_bytes"] = p.stat().st_size if p.exists() else 0
    result[e["act_slug"]] = status

    # code_of_criminal_procedure_1973 (must not use previous fallback html)
    e = by_slug["code_of_criminal_procedure_1973"]
    p = (
        RAW
        / "code_of_criminal_procedure_1973"
        / "code_of_criminal_procedure_1973_refetched.pdf"
    )
    status, chosen, reason = attempt_pdf_sources(
        e,
        [
            "https://www.indiacode.nic.in/handle/123456789/1611",
            "https://legislative.gov.in/sites/default/files/A1974-02.pdf",
        ],
        p,
        lambda t: (
            len(re.findall(r"(?im)^\s*(?:section|sec\.?|s\.)\s*\d+", t)) >= 250
            or "code of criminal procedure" in t.lower()
        ),
    )
    e["file_path"] = str(p).replace("\\", "/")
    e["source_url"] = chosen
    e["fetch_timestamp"] = now_iso()
    e["fetch_status"] = status
    e["fallback_reason"] = None if status == "success" else reason
    e["file_size_bytes"] = p.stat().st_size if p.exists() else 0
    result[e["act_slug"]] = status

    # criminal_rules_of_practice (kerala default, else placeholder)
    e = by_slug["criminal_rules_of_practice"]
    dest = (
        RAW
        / "criminal_rules_of_practice"
        / "criminal_rules_of_practice_kerala_high_court.html"
    )
    got_clean = False
    clean_source = ""
    for src in ["https://www.hckeralanic.in", "https://districts.ecourts.gov.in"]:
        try:
            st, body, _ = fetch_url(src)
            if st < 400:
                text = body.decode("utf-8", errors="ignore")
                if "rules" in text.lower() and "criminal" in text.lower():
                    save_bytes(dest, body)
                    got_clean = True
                    clean_source = src
                    break
        except Exception:
            continue
    if got_clean:
        e["file_path"] = str(dest).replace("\\", "/")
        e["source_url"] = clean_source
        e["fetch_status"] = "fallback_used"
        e["fallback_reason"] = "high-court site snapshot with rules references"
    else:
        placeholder = (
            RAW
            / "criminal_rules_of_practice"
            / "criminal_rules_of_practice_placeholder.md"
        )
        placeholder.parent.mkdir(parents=True, exist_ok=True)
        placeholder.write_text(
            "# Criminal Rules of Practice (Placeholder)\n\n"
            "Source gap: clean structured source not retrievable from Kerala High Court or eCourts endpoints during automated fetch.\n"
            "This placeholder should be replaced with official Criminal Rules PDF/HTML from a High Court rules repository.\n\n"
            "## Scope\n"
            "- Filing and registration in criminal proceedings\n"
            "- Process issuance and service\n"
            "- Bail and remand workflow\n"
            "- Evidence and witness handling\n"
            "- Judgment record and certified copies\n",
            encoding="utf-8",
        )
        e["file_path"] = str(placeholder).replace("\\", "/")
        e["source_url"] = "https://www.hckeralanic.in"
        e["fetch_status"] = "placeholder"
        e["fallback_reason"] = "No clean structured source found; generated placeholder"
    e["fetch_timestamp"] = now_iso()
    e["file_size_bytes"] = Path(e["file_path"]).stat().st_size
    result[e["act_slug"]] = e["fetch_status"]

    # bombay_high_court_rules
    e = by_slug["bombay_high_court_rules"]
    dest = RAW / "bombay_high_court_rules" / "bombay_high_court_rules_refetch.html"
    auth_blocked = True
    for src in [
        "https://bombayhighcourt.nic.in/generatenewauth.php",
        "https://bombayhighcourt.nic.in/libweb/rules/",
    ]:
        try:
            st, body, _ = fetch_url(src)
            if st >= 400:
                continue
            text = body.decode("utf-8", errors="ignore")
            tokenish = len(re.findall(r"\w+", text))
            if tokenish > 250 and "rule" in text.lower():
                save_bytes(dest, body)
                auth_blocked = False
                e["file_path"] = str(dest).replace("\\", "/")
                e["source_url"] = src
                e["fetch_status"] = "fallback_used"
                e["fallback_reason"] = "Fetched rules listing page"
                break
        except Exception:
            continue
    if auth_blocked:
        e["source_url"] = "https://bombayhighcourt.nic.in/generatenewauth.php"
        e["fetch_status"] = "failed - auth_wall"
        e["fallback_reason"] = "Rules content inaccessible due auth/session wall"
    e["fetch_timestamp"] = now_iso()
    e["file_size_bytes"] = (
        Path(e["file_path"]).stat().st_size if Path(e["file_path"]).exists() else 0
    )
    result[e["act_slug"]] = e["fetch_status"]

    # cpc_bnss_procedural_mapping_notes generated fresh
    e = by_slug["cpc_bnss_procedural_mapping_notes"]
    md = RAW / "cpc_bnss_procedural_mapping_notes" / "mapping_notes.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(
        "# CPC to BNSS Procedural Mapping Notes\n\n"
        "## CPC Order VI - Pleadings\n"
        "BNSS Equivalent: BNSS Chapter on pleadings and particulars in complaint/report drafting contexts\n"
        "Nature of change: procedure retained\n"
        "Notes: Core pleading discipline remains document-structure driven; BNSS adapts the framing for criminal process records.\n\n"
        "## CPC Order V - Summons\n"
        "BNSS Equivalent: BNSS provisions on summons and service of process\n"
        "Nature of change: substantive change\n"
        "Notes: BNSS expands electronic and modern service channels relative to legacy CPC-style service assumptions.\n\n"
        "## CPC Order XXXIX - Interim Relief / Injunctions\n"
        "BNSS Equivalent: BNSS interim protective directions and immediate judicial safeguards\n"
        "Nature of change: merged with X\n"
        "Notes: Injunction-like interim control in criminal process appears through protective and restraint-oriented sections instead of civil injunction terminology.\n\n"
        "## CPC Order XXI - Execution\n"
        "BNSS Equivalent: BNSS execution-enforcement and sentence/process execution chapters\n"
        "Nature of change: substantive change\n"
        "Notes: BNSS execution framework is criminal-enforcement centric and not decree-holder centric as in CPC.\n\n"
        "## CPC Orders XLI-XLIII - Appeals\n"
        "BNSS Equivalent: BNSS appellate provisions for convictions, acquittals, and sentence orders\n"
        "Nature of change: procedure retained\n"
        "Notes: Multi-tier appellate structure is retained with criminal-specific thresholds and standing.\n\n"
        "## CPC Orders XLVI-XLVII - Revision and Review\n"
        "BNSS Equivalent: BNSS revision and reference powers before superior courts\n"
        "Nature of change: merged with X\n"
        "Notes: Review language from CPC is partly redistributed into revision/reference supervisory mechanisms in criminal procedure.\n",
        encoding="utf-8",
    )
    e["source_url"] = "generated_internal_mapping_notes"
    e["file_path"] = str(md).replace("\\", "/")
    e["fetch_timestamp"] = now_iso()
    e["fetch_status"] = "generated"
    e["fallback_reason"] = "Generated as requested; not a fetchable source"
    e["file_size_bytes"] = md.stat().st_size
    result[e["act_slug"]] = "generated"

    return result


def parse_constitution(
    entry: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    text = load_text(Path(entry["file_path"]))
    base = make_base(entry)
    lines = text.split("\n")
    art_re = re.compile(r"^\s*article\s+([0-9]+[A-Za-z]?)\b[\.:\-\)]?\s*(.*)$", re.I)
    sch_re = re.compile(
        r"^\s*((?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|\d+(?:st|nd|rd|th))\s+schedule\b.*)$",
        re.I,
    )
    blocks: list[dict[str, str]] = []
    cur: dict[str, str] | None = None
    for line in lines:
        am = art_re.match(line.strip())
        sm = sch_re.match(line.strip())
        if am:
            if cur is not None:
                blocks.append(cur)
            cur = {
                "kind": "article",
                "key": am.group(1),
                "label": f"Article {am.group(1)}",
                "title": am.group(2).strip(),
                "body": "",
            }
            continue
        if sm:
            if cur is not None:
                blocks.append(cur)
            label = sm.group(1).strip()
            key = re.sub(r"[^A-Za-z0-9]+", "", label.split()[0])
            cur = {
                "kind": "schedule",
                "key": key,
                "label": label,
                "title": label,
                "body": "",
            }
            continue
        if cur is not None:
            cur["body"] += line + "\n"
    if cur is not None:
        blocks.append(cur)
    chunks = []
    for b in blocks:
        chunk_id = (
            f"constitution_art{b['key']}"
            if b["kind"] == "article"
            else f"constitution_sch{b['key']}"
        )
        section = b["label"] if b["kind"] == "article" else f"Schedule {b['label']}"
        txt = f"{section}. {b['title']}\n{b['body']}"
        chunks.append(make_chunk(base, chunk_id, section, b["title"], "", txt))
    if len(chunks) < 350:
        return chunks, "constitution parse likely incomplete"
    return chunks, None


def parse_statute_sections(
    entry: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    text = load_text(Path(entry["file_path"]))
    base = make_base(entry)
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
    chunks = []
    slug = entry["act_slug"]
    for b in blocks:
        txt = "\n".join(
            x
            for x in [
                b["chapter"],
                f"{b['label']}. {b['title']}".strip(),
                b["body"].strip(),
            ]
            if x
        )
        row = make_chunk(
            base, f"{slug}_s{b['no']}", b["label"], b["title"], b["chapter"], txt
        )
        chunks.append(row)
    if not chunks:
        return [], "no section blocks parsed"
    return chunks, None


def parse_order_rule_pdf(
    entry: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    text = load_text(Path(entry["file_path"]))
    base = make_base(entry)
    lines = text.split("\n")
    order_re = re.compile(r"^\s*order\s+([IVXLC0-9A-Za-z\-]+)\b\s*(.*)$", re.I)
    rule_re = re.compile(r"^\s*rule\s+([0-9]+[A-Za-z]?)\b[\.:\-\)]?\s*(.*)$", re.I)
    current_order = ""
    blocks: list[dict[str, str]] = []
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

    chunks = []
    slug = entry["act_slug"]
    for b in blocks:
        label = f"{b['order']} Rule {b['rule']}".strip()
        txt = "\n".join(x for x in [label, b["title"], b["body"].strip()] if x)
        key = re.sub(r"[^0-9A-Za-z]+", "_", label).strip("_")
        chunks.append(
            make_chunk(base, f"{slug}_{key}", label, b["title"], b["order"], txt)
        )
    if len(chunks) < 20:
        return chunks, "order-rule parse sparse"
    return chunks, None


def parse_mapping_notes(
    entry: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    text = read_md_text(Path(entry["file_path"]))
    base = make_base(entry)
    parts = re.split(r"(?m)^##\s+", text)
    chunks = []
    for part in parts[1:]:
        lines = part.splitlines()
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        cid = re.sub(r"[^0-9A-Za-z]+", "_", title).strip("_").lower()
        chunks.append(
            make_chunk(
                base,
                f"cpc_bnss_map_{cid}",
                title,
                title,
                "",
                f"{title}\n{body}",
            )
        )
    return chunks, None if chunks else "no mapping headings parsed"


def parse_placeholder_rules(
    entry: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    text = read_md_text(Path(entry["file_path"]))
    base = make_base(entry)
    rows = [
        make_chunk(
            base,
            "criminal_rules_placeholder_1",
            "Order Placeholder Rule 1",
            "Source Gap Notice",
            "Order Placeholder",
            text,
        )
    ]
    return rows, "placeholder source"


def apply_mappings_for_crpc() -> tuple[int, int]:
    path = CHUNKS / "code_of_criminal_procedure_1973.jsonl"
    rows = load_jsonl(path)
    mapping_path = MAPPINGS / "crpc_to_bnss.json"
    mapping: dict[str, Any] = {}
    if mapping_path.exists():
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    mapped = 0
    for row in rows:
        label = str(row.get("section_or_article") or "")
        m = re.search(r"(\d+[A-Za-z]?)", label)
        key = f"CrPC {m.group(1).upper()}" if m else ""
        value = mapping.get(key)
        row["mapped_to"] = None
        if isinstance(value, str) and value.upper().startswith("BNSS "):
            sec = value.split()[1]
            row["mapped_to"] = f"bharatiya_nagarik_suraksha_sanhita_2023_s{sec}"
            mapped += 1
    write_jsonl(path, rows)
    return mapped, len(rows)


def categorize(slug: str, count: int, avg: int, manifest_status: str, note: str) -> str:
    if slug in {
        "law_commission_report_47",
        "law_commission_report_69",
        "law_commission_report_152",
    }:
        return "BLOCKED_OCR"
    if manifest_status == "failed - auth_wall":
        return "BLOCKED_AUTH"
    if manifest_status == "placeholder":
        return "PLACEHOLDER"
    if count == 0:
        return "FAILED"
    if slug == "constitution_of_india" and count >= 450:
        return "CLEAN"
    if slug == "constitution_of_india" and count > 0:
        return "IMPROVED"
    if slug == "companies_act_2013" and count >= 200:
        return "IMPROVED"
    if slug == "code_of_criminal_procedure_1973" and count >= 250:
        return "IMPROVED"
    if slug == "supreme_court_rules_2013" and count >= 20:
        return "IMPROVED"
    if slug == "cpc_bnss_procedural_mapping_notes" and count >= 6:
        return "CLEAN"
    if avg >= 100:
        return "CLEAN"
    return "IMPROVED"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_slug = {m["act_slug"]: m for m in manifest}

    # Step 1: targeted refetch/generation
    refetch_status = refetch_targets(manifest)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Step 2: rechunk only refetched/generated successful-ish docs
    rechunked: dict[str, tuple[int, int, str]] = {}
    failed_parse: dict[str, str] = {}

    for slug in TARGET_SLUGS:
        entry = by_slug[slug]
        st = entry.get("fetch_status") or ""
        if st.startswith("failed"):
            failed_parse[slug] = entry.get("fallback_reason") or st
            out = CHUNKS / f"{slug}.jsonl"
            if out.exists():
                out.unlink()
            continue

        if slug == "constitution_of_india":
            rows, err = parse_constitution(entry)
        elif slug in {"companies_act_2013", "code_of_criminal_procedure_1973"}:
            rows, err = parse_statute_sections(entry)
        elif slug == "supreme_court_rules_2013":
            rows, err = parse_order_rule_pdf(entry)
        elif slug == "cpc_bnss_procedural_mapping_notes":
            rows, err = parse_mapping_notes(entry)
        elif slug == "criminal_rules_of_practice" and st == "placeholder":
            rows, err = parse_placeholder_rules(entry)
        elif slug == "criminal_rules_of_practice":
            rows, err = parse_order_rule_pdf(entry)
        elif slug == "bombay_high_court_rules":
            rows, err = parse_order_rule_pdf(entry)
        else:
            rows, err = ([], "unsupported")

        out = CHUNKS / f"{slug}.jsonl"
        if err and not rows:
            failed_parse[slug] = err
            if out.exists():
                out.unlink()
            continue
        write_jsonl(out, rows)
        rechunked[slug] = (len(rows), avg_tokens(rows), err or "ok")
        if err and st != "placeholder":
            failed_parse[slug] = err

    # keep mapped_to field for CrPC
    crpc_cov = apply_mappings_for_crpc()

    # Step 3: regenerate index + report
    by_tier = defaultdict(int)
    by_source_type = defaultdict(int)
    by_act: dict[str, Any] = {}
    superseded = []

    all_failed = []
    old_failed = []
    if INDEX.exists():
        old_failed = json.loads(INDEX.read_text(encoding="utf-8")).get(
            "failed_parse", []
        )

    for item in old_failed:
        if isinstance(item, dict):
            slug = item.get("act_slug")
            if slug and slug not in TARGET_SLUGS:
                all_failed.append(item)

    for slug, reason in failed_parse.items():
        all_failed.append({"act_slug": slug, "reason": reason})

    total = 0
    rows_by_slug: dict[str, list[dict[str, Any]]] = {}
    for entry in manifest:
        slug = entry["act_slug"]
        rows = load_jsonl(CHUNKS / f"{slug}.jsonl")
        rows_by_slug[slug] = rows
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
            "jsonl_path": f"legal_kb/chunks/{slug}.jsonl",
        }

    new_index = {
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
        "failed_parse": sorted(all_failed, key=lambda x: x.get("act_slug", "")),
    }
    INDEX.write_text(json.dumps(new_index, indent=2), encoding="utf-8")

    ipc_rows = rows_by_slug.get("indian_penal_code_1860", [])
    ev_rows = rows_by_slug.get("indian_evidence_act_1872", [])
    ipc_mapped = sum(1 for r in ipc_rows if r.get("mapped_to") is not None)
    ev_mapped = sum(1 for r in ev_rows if r.get("mapped_to") is not None)

    print("FINAL_TABLE_START")
    print("Act | Chunks | Avg Tokens | Status | Notes")
    for entry in manifest:
        slug = entry["act_slug"]
        rows = rows_by_slug[slug]
        count = len(rows)
        avg = avg_tokens(rows)
        manifest_status = str(entry.get("fetch_status") or "")
        note = ""
        if slug in rechunked:
            note = rechunked[slug][2]
        if slug in failed_parse and failed_parse[slug]:
            note = failed_parse[slug]
        if manifest_status in {"placeholder", "failed - auth_wall", "generated"}:
            note = (note + " | " if note else "") + manifest_status
        status = categorize(slug, count, avg, manifest_status, note)
        print(f"{slug} | {count} | {avg} | {status} | {note}")
    print("FINAL_TABLE_END")

    print(f"FINAL_TOTAL_CHUNKS: {new_index['total_chunks']}")
    print(f"MAPPING_COVERAGE IPC: {ipc_mapped} / {len(ipc_rows)}")
    print(f"MAPPING_COVERAGE CRPC: {crpc_cov[0]} / {crpc_cov[1]}")
    print(f"MAPPING_COVERAGE EVIDENCE: {ev_mapped} / {len(ev_rows)}")

    print("NOT_CLEAN_START")
    for entry in manifest:
        slug = entry["act_slug"]
        rows = rows_by_slug[slug]
        status = categorize(
            slug, len(rows), avg_tokens(rows), str(entry.get("fetch_status") or ""), ""
        )
        if status != "CLEAN":
            reason = ""
            if slug in failed_parse:
                reason = failed_parse[slug]
            elif entry.get("fetch_status") == "placeholder":
                reason = "placeholder generated due source gap"
            elif entry.get("fetch_status") == "failed - auth_wall":
                reason = "source behind auth wall"
            elif status == "IMPROVED":
                reason = "quality improved but may still be suboptimal"
            else:
                reason = "needs follow-up"
            print(f"{slug}: {status} - {reason}")
    print("NOT_CLEAN_END")
    print("INDEX_JSON_UPDATED: legal_kb/chunks/index.json")


if __name__ == "__main__":
    main()
