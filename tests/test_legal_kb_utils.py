"""Unit tests for legal KB preparation utilities."""

from src.features.legal_assistant.legal_kb import (
    LegalSource,
    build_chunk_id,
    build_chunks,
    split_legal_units,
    validate_chunk_metadata,
)


def test_split_legal_units_by_sections():
    """Section headings should produce multiple legal units."""
    text = (
        "Section 1 Short title and extent\nThis Act may be called...\n\n"
        "Section 2 Definitions\nIn this Act, unless context otherwise requires..."
    )
    units = split_legal_units(text, source_type="statute")
    assert len(units) == 2
    assert units[0][0].lower().startswith("section 1")
    assert units[1][0].lower().startswith("section 2")


def test_build_chunk_id_is_deterministic():
    """Chunk ID should be deterministic for same inputs."""
    one = build_chunk_id("ipc_1860", "Section 302", "abcdef1234567890")
    two = build_chunk_id("ipc_1860", "Section 302", "abcdef1234567890")
    assert one == two
    assert one.startswith("ipc_1860:")


def test_build_chunks_preserves_supersession_metadata():
    """Built chunks should keep superseded markers for legacy laws."""
    source = LegalSource(
        source_id="ipc_1860",
        source_type="statute",
        title="Indian Penal Code, 1860",
        act_name="Indian Penal Code, 1860",
        jurisdiction="india",
        year=1860,
        path="data/raw/legal_kb/ipc_1860.txt",
        source_url="https://example.test/ipc",
        is_superseded=True,
        superseded_by="Bharatiya Nyaya Sanhita, 2023",
    )
    text = (
        "Section 302 Punishment for murder\nWhoever commits murder shall be punished..."
    )
    chunks = build_chunks(source, text)
    assert len(chunks) == 1
    assert chunks[0].is_superseded is True
    assert chunks[0].superseded_by == "Bharatiya Nyaya Sanhita, 2023"


def test_validate_chunk_metadata_flags_missing_required_fields():
    """Metadata validator should report missing required fields."""
    source = LegalSource(
        source_id="constitution",
        source_type="constitution",
        title="Constitution",
        act_name="Constitution",
        jurisdiction="india",
        year=1950,
        path="dummy.txt",
        source_url=None,
        is_superseded=False,
        superseded_by=None,
    )
    chunks = build_chunks(
        source, "Article 14 Equality before law\nThe State shall not..."
    )
    chunks[0].section_or_article = ""
    errors = validate_chunk_metadata(chunks)
    assert any("missing section_or_article" in err for err in errors)
