"""
Extract text from legal document files.

Supported formats: PDF, DOCX
Primary PDF extractor: pdfplumber
Fallback PDF extractor: PyPDF2
DOCX extractor: python-docx

Clean extracted text:
- Remove excessive whitespace
- Remove page numbers (standalone numbers on lines)
- Normalize unicode characters
- Strip headers/footers heuristically

Return empty string on failure (never raise).
"""

from pathlib import Path
import re
import unicodedata

import pdfplumber
import PyPDF2
from docx import Document
from loguru import logger


class DocumentProcessor:
    """Extract and clean text from legal documents."""

    def extract_text(self, file_path: Path) -> str:
        """Detect format from extension and extract text.

        .pdf -> extract_from_pdf()
        .docx -> extract_from_docx()
        Other -> return ""

        Args:
            file_path: Path to document.

        Returns:
            Extracted text string.
        """
        suffix = file_path.suffix.lower()
        try:
            if suffix == ".pdf":
                return self.extract_from_pdf(file_path)
            if suffix == ".docx":
                return self.extract_from_docx(file_path)
            logger.warning("Unsupported document format", file=str(file_path))
            return ""
        except Exception as exc:
            logger.error("Document extraction failed", file=str(file_path), error=str(exc))
            return ""

    def extract_from_pdf(self, file_path: Path) -> str:
        """Try pdfplumber first, fall back to PyPDF2.

        Args:
            file_path: Path to PDF.

        Returns:
            Extracted text string.
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                pages = []
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    pages.append(page_text)
                text = "\n\n".join(pages)
            logger.info("PDF extracted with pdfplumber", file=str(file_path))
            return self.clean_text(text)
        except Exception as exc:
            logger.warning("pdfplumber failed, falling back", file=str(file_path), error=str(exc))

        try:
            with open(file_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                pages = []
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    pages.append(page_text)
            text = "\n\n".join(pages)
            logger.info("PDF extracted with PyPDF2", file=str(file_path))
            return self.clean_text(text)
        except Exception as exc:
            logger.error("PDF extraction failed", file=str(file_path), error=str(exc))
            return ""

    def extract_from_docx(self, file_path: Path) -> str:
        """Extract all paragraphs from DOCX, join with newlines.

        Args:
            file_path: Path to DOCX.

        Returns:
            Extracted text string.
        """
        try:
            doc = Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text]
            text = "\n".join(paragraphs)
            logger.info("DOCX extracted", file=str(file_path))
            return self.clean_text(text)
        except Exception as exc:
            logger.error("DOCX extraction failed", file=str(file_path), error=str(exc))
            return ""

    def clean_text(self, text: str) -> str:
        """Clean extracted text.

        Remove: excessive whitespace, standalone page numbers
        Normalize: unicode, line endings

        Args:
            text: Raw text.

        Returns:
            Cleaned text.
        """
        if not text:
            return ""

        text = unicodedata.normalize("NFKC", text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

        lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            if re.match(r"^\d{1,4}$", stripped):
                continue
            lines.append(stripped)
        cleaned = "\n".join(lines).strip()
        return cleaned
