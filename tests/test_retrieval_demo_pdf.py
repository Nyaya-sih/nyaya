"""Offline checks for the curated, fictional retrieval input document."""

from io import BytesIO

from PyPDF2 import PdfReader

from scripts.generate_retrieval_demo import generate_pdf


def test_retrieval_demo_is_reproducible_and_selectable(tmp_path):
    output = tmp_path / "retrieval.pdf"
    generate_pdf(output)
    first = output.read_bytes()
    generate_pdf(output)
    assert output.read_bytes() == first
    pages = PdfReader(BytesIO(first)).pages
    assert len(pages) == 2
    text = "\n".join(page.extract_text() for page in pages)
    for page in pages:
        assert "FICTIONAL FACTS" in page.extract_text()
        assert "NOT A REAL JUDGMENT" in page.extract_text()
    for expected in ["Section 438", "307", "Aman Prakash", "simple injuries",
                     "No outcome determined", "Historical legal setting"]:
        assert expected in text
    assert "0.8030" not in text
    assert "Manoj Kumar" not in text
