"""Legal knowledge-base preparation utilities for Phase 3."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
import json
import re
from typing import Any, Iterable

from loguru import logger

from src.utils.document_processor import DocumentProcessor


@dataclass
class LegalSource:
    """Source metadata for a legal corpus document."""

    source_id: str
    source_type: str
    title: str
    act_name: str
    jurisdiction: str
    year: int | None
    path: str
    source_url: str | None
    is_superseded: bool
    superseded_by: str | None


@dataclass
class LegalChunk:
    """Prepared KB chunk ready for embedding."""

    chunk_id: str
    source_id: str
    source_type: str
    title: str
    act_name: str
    section_or_article: str
    chapter_or_part: str | None
    text: str
    year: int | None
    jurisdiction: str
    is_superseded: bool
    superseded_by: str | None
    source_url: str | None
    source_version_hash: str


def load_sources_manifest(manifest_path: Path) -> list[LegalSource]:
    """Load legal source manifest from JSON file."""
    if not manifest_path.exists():
        return []
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    sources: list[LegalSource] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id", "")).strip()
        title = str(item.get("title", "")).strip()
        path = str(item.get("path", "")).strip()
        if not source_id or not title or not path:
            continue
        sources.append(
            LegalSource(
                source_id=source_id,
                source_type=str(item.get("source_type", "statute")).strip()
                or "statute",
                title=title,
                act_name=str(item.get("act_name", title)).strip() or title,
                jurisdiction=str(item.get("jurisdiction", "india")).strip() or "india",
                year=_to_optional_int(item.get("year")),
                path=path,
                source_url=_to_optional_str(item.get("source_url")),
                is_superseded=bool(item.get("is_superseded", False)),
                superseded_by=_to_optional_str(item.get("superseded_by")),
            )
        )
    return sources


def write_manifest_template(manifest_path: Path) -> None:
    """Write a starter manifest template for legal KB ingestion."""
    template = [
        {
            "source_id": "constitution_of_india",
            "source_type": "constitution",
            "title": "Constitution of India",
            "act_name": "Constitution of India",
            "jurisdiction": "india",
            "year": 1950,
            "path": "data/raw/legal_kb/constitution_of_india.txt",
            "source_url": "https://www.indiacode.nic.in/",
            "is_superseded": False,
            "superseded_by": None,
        },
        {
            "source_id": "ipc_1860",
            "source_type": "statute",
            "title": "Indian Penal Code, 1860",
            "act_name": "Indian Penal Code, 1860",
            "jurisdiction": "india",
            "year": 1860,
            "path": "data/raw/legal_kb/ipc_1860.txt",
            "source_url": "https://www.indiacode.nic.in/",
            "is_superseded": True,
            "superseded_by": "Bharatiya Nyaya Sanhita, 2023",
        },
    ]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(template, indent=2), encoding="utf-8")


def read_legal_text(source_path: Path) -> str:
    """Read legal source text from txt/md/html/pdf/docx."""
    suffix = source_path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return source_path.read_text(encoding="utf-8", errors="ignore")
    if suffix in {".html", ".htm"}:
        raw = source_path.read_text(encoding="utf-8", errors="ignore")
        return _strip_html(raw)
    if suffix in {".pdf", ".docx"}:
        return DocumentProcessor().extract_text(source_path)
    logger.warning("Unsupported legal source format", path=str(source_path))
    return ""


def split_legal_units(text: str, source_type: str) -> list[tuple[str, str]]:
    """Split text by legal unit headings.

    Returns tuples of (unit_label, unit_text).
    """
    normalized = normalize_text(text)
    if not normalized:
        return []

    heading_patterns = [
        re.compile(r"(?im)^\s*(section\s+\d+[a-zA-Z\-]*)\b"),
        re.compile(r"(?im)^\s*(article\s+\d+[a-zA-Z\-]*)\b"),
        re.compile(r"(?im)^\s*(rule\s+\d+[a-zA-Z\-]*)\b"),
        re.compile(r"(?im)^\s*(order\s+[ivxlcdm0-9]+)\b"),
        re.compile(r"(?im)^\s*(chapter\s+[ivxlcdm0-9a-z\-]+)\b"),
    ]

    # Prefer domain-specific pattern ordering.
    if source_type == "constitution":
        heading_patterns = [heading_patterns[1], *heading_patterns]
    elif source_type in {"rules", "procedural"}:
        heading_patterns = [heading_patterns[2], heading_patterns[3], *heading_patterns]

    match_positions: list[tuple[int, str]] = []
    for pattern in heading_patterns:
        for match in pattern.finditer(normalized):
            match_positions.append((match.start(), match.group(1).strip()))

    if not match_positions:
        return [("document", normalized)]

    dedup_by_pos: dict[int, str] = {}
    for pos, label in sorted(match_positions, key=lambda item: item[0]):
        if pos not in dedup_by_pos:
            dedup_by_pos[pos] = label

    sorted_positions = sorted(dedup_by_pos.items(), key=lambda item: item[0])
    chunks: list[tuple[str, str]] = []
    for idx, (start, label) in enumerate(sorted_positions):
        end = (
            sorted_positions[idx + 1][0]
            if idx + 1 < len(sorted_positions)
            else len(normalized)
        )
        chunk_text = normalized[start:end].strip()
        if len(chunk_text) < 30:
            continue
        chunks.append((label, chunk_text))

    return chunks or [("document", normalized)]


def build_chunks(source: LegalSource, raw_text: str) -> list[LegalChunk]:
    """Build structured legal KB chunks from a source text."""
    units = split_legal_units(raw_text, source.source_type)
    version_hash = sha1(normalize_text(raw_text).encode("utf-8")).hexdigest()
    chunks: list[LegalChunk] = []
    for unit_label, unit_text in units:
        clean_text = unit_text.strip()
        if len(clean_text) < 30:
            continue
        section_or_article = unit_label
        chunk_id = build_chunk_id(
            source_id=source.source_id,
            section_or_article=section_or_article,
            source_version_hash=version_hash,
        )
        chunks.append(
            LegalChunk(
                chunk_id=chunk_id,
                source_id=source.source_id,
                source_type=source.source_type,
                title=source.title,
                act_name=source.act_name,
                section_or_article=section_or_article,
                chapter_or_part=extract_chapter_or_part(clean_text),
                text=clean_text,
                year=source.year,
                jurisdiction=source.jurisdiction,
                is_superseded=source.is_superseded,
                superseded_by=source.superseded_by,
                source_url=source.source_url,
                source_version_hash=version_hash,
            )
        )
    return chunks


def build_chunk_id(
    source_id: str, section_or_article: str, source_version_hash: str
) -> str:
    """Build deterministic chunk identifier."""
    unit_slug = slugify(section_or_article)
    return f"{source_id}:{unit_slug}:{source_version_hash[:16]}"


def validate_chunk_metadata(chunks: Iterable[LegalChunk]) -> list[str]:
    """Validate mandatory chunk metadata fields."""
    errors: list[str] = []
    for chunk in chunks:
        if not chunk.chunk_id:
            errors.append("missing chunk_id")
        if not chunk.act_name:
            errors.append(f"missing act_name: {chunk.chunk_id}")
        if not chunk.section_or_article:
            errors.append(f"missing section_or_article: {chunk.chunk_id}")
        if not chunk.source_type:
            errors.append(f"missing source_type: {chunk.chunk_id}")
        if not chunk.text:
            errors.append(f"missing text: {chunk.chunk_id}")
    return errors


def normalize_text(text: str) -> str:
    """Normalize text whitespace for chunking."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_chapter_or_part(text: str) -> str | None:
    """Extract chapter/part label from chunk text."""
    pattern = re.compile(r"(?im)^\s*(chapter|part)\s+([ivxlcdm0-9a-z\-]+)\b")
    match = pattern.search(text)
    if not match:
        return None
    return f"{match.group(1).title()} {match.group(2).upper()}"


def slugify(value: str) -> str:
    """Create ASCII-ish slug for IDs."""
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "unit"


def _to_optional_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _strip_html(raw: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return normalize_text(text)
