"""Local-only document extraction for courtroom uploads."""

from io import BytesIO
from pathlib import Path
from typing import Optional

from docx import Document
from docx.table import Table
from fastapi import APIRouter, File, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel, Field
from PyPDF2 import PdfReader


router = APIRouter(prefix="/api/v1/courtroom", tags=["Courtroom"])
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 120_000


class DocumentExtractionResponse(BaseModel):
    """Extracted upload text and any limitations affecting its completeness."""

    text: str
    filename: str
    page_count: Optional[int] = None
    extracted_characters: int
    truncated: bool
    warnings: list[str] = Field(default_factory=list)


@router.post("/document", response_model=DocumentExtractionResponse)
def extract_document(file: UploadFile = File(...)) -> DocumentExtractionResponse:
    """Extract bounded text from a PDF, DOCX, or UTF-8 TXT upload."""
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(400, "Only PDF, DOCX, and TXT files are supported.")

    try:
        content = file.file.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(413, "Document must not exceed 10 MB.")
        if not content:
            raise HTTPException(422, "Document is empty.")

        page_count = None
        warnings = []
        if extension == ".txt":
            text = content.decode("utf-8-sig")
            if "\x00" in text:
                raise ValueError("Binary content in TXT document")
            parts = [text]
        else:
            stream = BytesIO(content)
            if extension == ".pdf":
                reader = PdfReader(stream)
                if reader.is_encrypted and not reader.decrypt(""):
                    raise HTTPException(
                        422, "PDF is encrypted and cannot be read without a password."
                    )
                page_count = len(reader.pages)
                parts = reader.pages
            else:
                document = Document(stream)
                parts = (
                    "\n".join("\t".join(cell.text for cell in row.cells)
                              for row in block.rows)
                    if isinstance(block, Table) else block.text
                    for block in document.iter_inner_content()
                )

        chunks = []
        remaining = MAX_TEXT_CHARS
        truncated = False
        has_text = False
        for page_number, part in enumerate(parts, 1):
            if extension == ".pdf":
                part = part.extract_text() or ""
                if not part.strip():
                    warnings.append(
                        f"PDF page {page_number} has no extractable text; it may be "
                        "blank or scanned. OCR is not performed."
                    )
                has_text = has_text or bool(part.strip())
                part = f"[PDF page {page_number}]\n{part}"
            else:
                has_text = has_text or bool(part.strip())
            chunk = ("\n" if chunks else "") + part
            truncated = truncated or len(chunk) > remaining
            if remaining:
                chunks.append(chunk[:remaining])
                remaining -= len(chunks[-1])

        text = "".join(chunks).strip()
        if not has_text or not text:
            detail = "Document contains no extractable text."
            if warnings:
                detail += " " + " ".join(warnings)
            raise HTTPException(422, detail)
        if truncated:
            warnings.append(
                f"Extracted text was truncated to {MAX_TEXT_CHARS:,} characters; "
                "additional document content was omitted."
            )
        return DocumentExtractionResponse(
            text=text,
            filename=filename,
            page_count=page_count,
            extracted_characters=len(text),
            truncated=truncated,
            warnings=warnings,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Courtroom document extraction failed", error=str(exc))
        raise HTTPException(422, "Unable to extract text from document.") from exc
