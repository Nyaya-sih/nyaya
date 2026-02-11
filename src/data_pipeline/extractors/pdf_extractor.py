"""
PDF text extraction module.
Extracts clean text from legal PDF documents using multiple strategies.
"""
import re
from pathlib import Path
from typing import Optional, Dict, List
import pdfplumber
import PyPDF2
from loguru import logger


class PDFExtractor:
    """
    Extract text from PDF documents with multiple fallback strategies.
    """

    def __init__(self):
        """Initialize PDF extractor."""
        logger.info("PDF extractor initialized")

    def extract_text(self, pdf_path: Path) -> Dict[str, any]:
        """
        Extract text from PDF with metadata.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary containing:
                - text: Cleaned full text
                - page_count: Number of pages
                - pages: List of per-page text
                - extraction_method: Method used (pdfplumber/pypdf2)
                - success: Boolean indicating success
                - error: Error message if failed
        """
        logger.info(f"Extracting text from PDF", file=str(pdf_path))

        result = {
            "text": "",
            "page_count": 0,
            "pages": [],
            "extraction_method": None,
            "success": False,
            "error": None
        }

        if not pdf_path.exists():
            result["error"] = f"File not found: {pdf_path}"
            logger.error(result["error"])
            return result

        # Try pdfplumber first (better for formatted documents)
        try:
            result = self._extract_with_pdfplumber(pdf_path)
            if result["success"] and result["text"].strip():
                return result
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed, trying PyPDF2", error=str(e))

        # Fallback to PyPDF2
        try:
            result = self._extract_with_pypdf2(pdf_path)
            if result["success"]:
                return result
        except Exception as e:
            logger.error(f"All extraction methods failed", file=str(pdf_path), error=str(e))
            result["error"] = f"All extraction methods failed: {str(e)}"

        return result

    def _extract_with_pdfplumber(self, pdf_path: Path) -> Dict[str, any]:
        """Extract text using pdfplumber (primary method)."""
        result = {
            "text": "",
            "page_count": 0,
            "pages": [],
            "extraction_method": "pdfplumber",
            "success": False,
            "error": None
        }

        try:
            with pdfplumber.open(pdf_path) as pdf:
                result["page_count"] = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            cleaned_text = self._clean_text(page_text)
                            result["pages"].append({
                                "page_number": page_num,
                                "text": cleaned_text
                            })
                            result["text"] += cleaned_text + "\n\n"
                    except Exception as e:
                        logger.warning(f"Failed to extract page {page_num}", error=str(e))
                        result["pages"].append({
                            "page_number": page_num,
                            "text": "",
                            "error": str(e)
                        })

                result["success"] = len(result["text"].strip()) > 0
                logger.debug(
                    f"pdfplumber extraction complete",
                    pages=result["page_count"],
                    text_length=len(result["text"])
                )

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"pdfplumber extraction failed", error=str(e))

        return result

    def _extract_with_pypdf2(self, pdf_path: Path) -> Dict[str, any]:
        """Extract text using PyPDF2 (fallback method)."""
        result = {
            "text": "",
            "page_count": 0,
            "pages": [],
            "extraction_method": "pypdf2",
            "success": False,
            "error": None
        }

        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                result["page_count"] = len(pdf_reader.pages)

                for page_num, page in enumerate(pdf_reader.pages, 1):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            cleaned_text = self._clean_text(page_text)
                            result["pages"].append({
                                "page_number": page_num,
                                "text": cleaned_text
                            })
                            result["text"] += cleaned_text + "\n\n"
                    except Exception as e:
                        logger.warning(f"Failed to extract page {page_num}", error=str(e))
                        result["pages"].append({
                            "page_number": page_num,
                            "text": "",
                            "error": str(e)
                        })

                result["success"] = len(result["text"].strip()) > 0
                logger.debug(
                    f"PyPDF2 extraction complete",
                    pages=result["page_count"],
                    text_length=len(result["text"])
                )

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"PyPDF2 extraction failed", error=str(e))

        return result

    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text.

        Args:
            text: Raw extracted text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Normalize line breaks
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # Remove excessive whitespace
        text = re.sub(r' +', ' ', text)  # Multiple spaces to single space
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines to double newline

        # Fix common OCR/encoding issues
        text = text.replace('\x00', '')  # Remove null bytes
        text = text.replace('\ufffd', '')  # Remove replacement character

        # Remove page numbers (common patterns)
        # Pattern: standalone numbers at start or end of lines
        text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)

        # Strip leading/trailing whitespace from each line
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        return text.strip()

    def extract_metadata_from_pdf(self, pdf_path: Path) -> Dict[str, any]:
        """
        Extract PDF metadata (not case metadata).

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary with PDF metadata
        """
        metadata = {
            "file_path": str(pdf_path),
            "file_name": pdf_path.name,
            "file_size": pdf_path.stat().st_size if pdf_path.exists() else 0,
            "page_count": 0,
            "title": None,
            "author": None,
            "subject": None,
            "creator": None,
            "producer": None,
            "creation_date": None,
        }

        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                metadata["page_count"] = len(pdf_reader.pages)

                if pdf_reader.metadata:
                    metadata["title"] = pdf_reader.metadata.get("/Title")
                    metadata["author"] = pdf_reader.metadata.get("/Author")
                    metadata["subject"] = pdf_reader.metadata.get("/Subject")
                    metadata["creator"] = pdf_reader.metadata.get("/Creator")
                    metadata["producer"] = pdf_reader.metadata.get("/Producer")
                    metadata["creation_date"] = pdf_reader.metadata.get("/CreationDate")

        except Exception as e:
            logger.error(f"Failed to extract PDF metadata", file=str(pdf_path), error=str(e))
            metadata["error"] = str(e)

        return metadata

    def is_scanned_pdf(self, pdf_path: Path, sample_pages: int = 3) -> bool:
        """
        Heuristic to detect if PDF is scanned (needs OCR).

        Args:
            pdf_path: Path to PDF file
            sample_pages: Number of pages to sample

        Returns:
            True if likely scanned, False otherwise
        """
        try:
            extraction_result = self.extract_text(pdf_path)

            if not extraction_result["success"]:
                return True  # If extraction failed, likely scanned

            # Check text density
            text_length = len(extraction_result["text"])
            page_count = extraction_result["page_count"]

            # If less than 100 characters per page on average, likely scanned
            avg_chars_per_page = text_length / page_count if page_count > 0 else 0

            if avg_chars_per_page < 100:
                logger.info(f"PDF appears to be scanned", file=str(pdf_path), avg_chars=avg_chars_per_page)
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to check if PDF is scanned", file=str(pdf_path), error=str(e))
            return True  # Assume scanned if check fails
