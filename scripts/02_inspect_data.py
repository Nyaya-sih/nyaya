#!/usr/bin/env python3
"""
Script to inspect downloaded data.
Analyzes PDFs, extracts sample text, and shows statistics.
"""
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_logging
from src.data_pipeline.downloaders.hc_downloader import HighCourtDownloader
from src.data_pipeline.extractors.pdf_extractor import PDFExtractor
from loguru import logger


def main():
    """Inspect downloaded data."""
    # Setup logging
    setup_logging()

    logger.info("=" * 80)
    logger.info("DATA INSPECTION TOOL")
    logger.info("=" * 80)

    # Initialize components
    downloader = HighCourtDownloader()
    pdf_extractor = PDFExtractor()

    # Get all downloaded PDFs
    logger.info("Scanning for downloaded PDFs...")
    pdf_files = downloader.get_downloaded_pdfs()

    if not pdf_files:
        logger.error("No PDF files found. Please run 01_download_sample.py first.")
        sys.exit(1)

    logger.info(f"Found {len(pdf_files)} PDF files")
    logger.info("")

    # Analyze files
    logger.info("=" * 80)
    logger.info("FILE STATISTICS")
    logger.info("=" * 80)

    total_size = sum(f.stat().st_size for f in pdf_files)
    avg_size = total_size / len(pdf_files)

    logger.info(f"Total files: {len(pdf_files)}")
    logger.info(f"Total size: {total_size / (1024*1024):.2f} MB")
    logger.info(f"Average file size: {avg_size / 1024:.2f} KB")
    logger.info("")

    # Group by court
    logger.info("Files by court:")
    courts = {}
    for pdf in pdf_files:
        court = pdf.parent.parent.name
        courts[court] = courts.get(court, 0) + 1

    for court, count in sorted(courts.items()):
        logger.info(f"  {court}: {count} files")
    logger.info("")

    # Extract text from sample files
    logger.info("=" * 80)
    logger.info("TEXT EXTRACTION SAMPLE")
    logger.info("=" * 80)

    sample_files = pdf_files[:3]  # Sample 3 files
    logger.info(f"Extracting text from {len(sample_files)} sample files...")
    logger.info("")

    for i, pdf_path in enumerate(sample_files, 1):
        logger.info(f"Sample {i}: {pdf_path.name}")
        logger.info("-" * 80)

        # Extract metadata
        pdf_metadata = pdf_extractor.extract_metadata_from_pdf(pdf_path)
        logger.info(f"  File size: {pdf_metadata['file_size'] / 1024:.2f} KB")
        logger.info(f"  Pages: {pdf_metadata['page_count']}")

        # Extract text
        extraction_result = pdf_extractor.extract_text(pdf_path)

        if extraction_result["success"]:
            logger.info(f"  Extraction method: {extraction_result['extraction_method']}")
            logger.info(f"  Text length: {len(extraction_result['text'])} characters")

            # Check if scanned
            is_scanned = pdf_extractor.is_scanned_pdf(pdf_path)
            logger.info(f"  Appears to be scanned: {is_scanned}")

            # Show first 500 characters
            text_preview = extraction_result['text'][:500]
            logger.info(f"  Text preview:")
            logger.info(f"  {'-' * 40}")
            for line in text_preview.split('\n')[:10]:
                logger.info(f"  {line}")
            logger.info(f"  {'-' * 40}")
        else:
            logger.error(f"  Extraction failed: {extraction_result['error']}")

        logger.info("")

    # Check for metadata JSON files
    logger.info("=" * 80)
    logger.info("METADATA FILES")
    logger.info("=" * 80)

    json_files = list(downloader.output_dir.rglob("*.json"))
    logger.info(f"Found {len(json_files)} JSON files")

    if json_files:
        # Sample a metadata file
        sample_json = json_files[0]
        logger.info(f"Sample metadata file: {sample_json.name}")

        try:
            with open(sample_json, 'r') as f:
                metadata = json.load(f)

            logger.info("Metadata structure:")
            for key in metadata.keys():
                logger.info(f"  - {key}")

            logger.info("")
            logger.info("Sample metadata content:")
            logger.info(json.dumps(metadata, indent=2)[:500])

        except Exception as e:
            logger.error(f"Failed to read metadata: {e}")

    logger.info("")
    logger.info("=" * 80)
    logger.info("RECOMMENDATIONS")
    logger.info("=" * 80)

    # Provide recommendations
    scanned_count = 0
    for pdf in pdf_files[:10]:  # Check first 10
        if pdf_extractor.is_scanned_pdf(pdf):
            scanned_count += 1

    if scanned_count > 5:
        logger.warning("⚠️  Many files appear to be scanned PDFs")
        logger.warning("   OCR may be needed for accurate text extraction")
    else:
        logger.info("✅ Most files are digital PDFs with extractable text")

    logger.info("")
    logger.info("Next step: Run 03_run_extraction.py to extract structured metadata")


if __name__ == "__main__":
    main()
