#!/usr/bin/env python3
"""
Script to run the complete extraction pipeline.
Extracts text, runs LLM extraction, validates, and loads to database.
"""

import sys
import time
from pathlib import Path
from typing import List
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_logging
from src.data_pipeline.downloaders.hc_downloader import HighCourtDownloader
from src.data_pipeline.extractors.pdf_extractor import PDFExtractor
from src.data_pipeline.extractors.metadata_extractor import MetadataExtractor
from src.data_pipeline.validators.data_validator import DataValidator
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from src.database.schemas import ExtractionResult, ProcessingStats
from src.config.settings import settings
from loguru import logger


def process_single_case(
    pdf_path: Path,
    pdf_extractor: PDFExtractor,
    metadata_extractor: MetadataExtractor,
    validator: DataValidator,
) -> ExtractionResult:
    """
    Process a single case PDF.

    Args:
        pdf_path: Path to PDF file
        pdf_extractor: PDF extractor instance
        metadata_extractor: Metadata extractor instance
        validator: Validator instance

    Returns:
        ExtractionResult object
    """
    start_time = time.time()

    try:
        # Extract text from PDF
        logger.debug(f"Extracting text from PDF", file=pdf_path.name)
        pdf_result = pdf_extractor.extract_text(pdf_path)

        if not pdf_result["success"]:
            raise Exception(f"PDF extraction failed: {pdf_result.get('error')}")

        full_text = pdf_result["text"]
        page_count = pdf_result["page_count"]

        # Extract metadata using LLM
        logger.debug(f"Extracting metadata with LLM", file=pdf_path.name)
        metadata = metadata_extractor.extract_case_metadata(
            judgment_text=full_text, case_id=pdf_path.stem
        )

        # Validate extracted metadata
        logger.debug(f"Validating metadata", file=pdf_path.name)
        validation = validator.validate(metadata)

        # Create extraction result
        extraction_time = time.time() - start_time

        result = ExtractionResult(
            metadata=metadata,
            full_text=full_text,
            validation=validation,
            extraction_model=metadata_extractor.llm_client.model,
            extraction_time=extraction_time,
            source_file=str(pdf_path),
            page_count=page_count,
        )

        logger.info(
            f"Case processed successfully",
            file=pdf_path.name,
            valid=validation.is_valid,
            avg_confidence=f"{metadata.get_average_confidence():.2f}",
            time=f"{extraction_time:.2f}s",
        )

        return result

    except Exception as e:
        logger.error(f"Failed to process case", file=pdf_path.name, error=str(e))
        raise


def main():
    """Run the extraction pipeline."""
    # Setup logging
    setup_logging()

    logger.info("=" * 80)
    logger.info("METADATA EXTRACTION PIPELINE")
    logger.info("=" * 80)

    # Check if LLM API key is configured
    if not settings.has_llm_key():
        logger.error("No LLM API key configured!")
        logger.error(
            "Please set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GEMINI_API_KEY in .env file"
        )
        sys.exit(1)

    logger.info(f"Using LLM: {settings.extraction_model}")
    logger.info(f"Available providers: {', '.join(settings.get_available_models())}")
    logger.info("")

    # Initialize components
    logger.info("Initializing components...")
    downloader = HighCourtDownloader()
    pdf_extractor = PDFExtractor()
    metadata_extractor = MetadataExtractor()
    validator = DataValidator()
    db_loader = DatabaseLoader()

    # Initialize database
    logger.info("Initializing database...")
    try:
        db_loader.init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        logger.error("Make sure PostgreSQL is running: docker-compose up -d postgres")
        sys.exit(1)

    # Get downloaded PDFs
    logger.info("Scanning for PDF files...")
    pdf_files = downloader.get_downloaded_pdfs()

    if not pdf_files:
        logger.error("No PDF files found. Please run 01_download_sample.py first.")
        sys.exit(1)

    logger.info(f"Found {len(pdf_files)} PDF files")
    logger.info("")

    # Ask user for confirmation
    logger.info(
        f"This will process {len(pdf_files)} cases using {settings.extraction_model}"
    )
    logger.info(f"Estimated cost: ~${len(pdf_files) * 0.01:.2f} (rough estimate)")
    logger.info("")

    response = input("Do you want to continue? (y/n): ")
    if response.lower() != "y":
        logger.info("Cancelled by user")
        sys.exit(0)

    # Process cases
    logger.info("")
    logger.info("=" * 80)
    logger.info("PROCESSING CASES")
    logger.info("=" * 80)

    stats = ProcessingStats()
    extraction_results: List[ExtractionResult] = []

    for pdf_path in tqdm(pdf_files, desc="Processing cases"):
        stats.total_cases += 1

        try:
            result = process_single_case(
                pdf_path=pdf_path,
                pdf_extractor=pdf_extractor,
                metadata_extractor=metadata_extractor,
                validator=validator,
            )

            extraction_results.append(result)
            stats.successful_extractions += 1

            # Accumulate confidence scores
            stats.average_confidence += result.metadata.get_average_confidence()

        except Exception as e:
            stats.failed_extractions += 1
            stats.extraction_errors.append({"file": pdf_path.name, "error": str(e)})

    # Calculate statistics
    stats.processing_time = sum(r.extraction_time for r in extraction_results)
    if stats.successful_extractions > 0:
        stats.average_confidence /= stats.successful_extractions

    # Get LLM statistics
    llm_stats = metadata_extractor.llm_client.get_stats()
    stats.estimated_cost = llm_stats["estimated_cost"]

    # Load to database
    logger.info("")
    logger.info("=" * 80)
    logger.info("LOADING TO DATABASE")
    logger.info("=" * 80)

    loading_stats = db_loader.load_batch(extraction_results)

    # Print summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("EXTRACTION SUMMARY")
    logger.info("=" * 80)

    logger.info(f"Processing:")
    logger.info(f"  Total cases: {stats.total_cases}")
    logger.info(f"  Successful: {stats.successful_extractions}")
    logger.info(f"  Failed: {stats.failed_extractions}")
    logger.info(
        f"  Success rate: {stats.successful_extractions / stats.total_cases * 100:.1f}%"
    )
    logger.info("")

    logger.info(f"Quality:")
    logger.info(f"  Average confidence: {stats.average_confidence:.2f}")
    logger.info("")

    logger.info(f"LLM Usage:")
    logger.info(f"  Provider: {llm_stats['provider']}")
    logger.info(f"  Model: {llm_stats['model']}")
    logger.info(f"  Total requests: {llm_stats['total_requests']}")
    logger.info(f"  Total tokens: {llm_stats['total_tokens']:,}")
    logger.info(f"  Estimated cost: ${stats.estimated_cost:.4f}")
    logger.info("")

    logger.info(f"Database:")
    logger.info(f"  Successfully loaded: {loading_stats['successful']}")
    logger.info(f"  Duplicates skipped: {loading_stats['duplicates']}")
    logger.info(f"  Failed: {loading_stats['failed']}")
    logger.info("")

    # Database statistics
    db_stats = db_loader.get_database_stats()
    logger.info(f"Database Statistics:")
    logger.info(f"  Total cases: {db_stats['total_cases']}")
    logger.info(f"  Valid: {db_stats['valid_cases']}")
    logger.info(f"  Needs review: {db_stats['needs_review']}")
    logger.info(f"  Invalid: {db_stats['invalid_cases']}")
    logger.info(f"  Total statutes: {db_stats['total_statutes']}")
    logger.info(f"  Total precedents: {db_stats['total_precedents']}")
    logger.info("")

    # Show errors if any
    if stats.extraction_errors:
        logger.warning(f"Extraction errors ({len(stats.extraction_errors)}):")
        for err in stats.extraction_errors[:5]:  # Show first 5
            logger.warning(f"  {err['file']}: {err['error']}")
        if len(stats.extraction_errors) > 5:
            logger.warning(f"  ... and {len(stats.extraction_errors) - 5} more")

    logger.info("")
    logger.info("✅ Extraction pipeline complete!")
    logger.info("")
    logger.info("Next step: Run 04_validate_quality.py to review extraction quality")


if __name__ == "__main__":
    main()
