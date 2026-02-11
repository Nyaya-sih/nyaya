#!/usr/bin/env python3
"""
Simplified extraction script for sample PDFs.
Runs the complete pipeline: PDF extraction → LLM metadata extraction → Database loading.
"""
import sys
import time
import json
from pathlib import Path
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_logging
from src.data_pipeline.extractors.pdf_extractor import PDFExtractor
from src.data_pipeline.extractors.metadata_extractor import MetadataExtractor
from src.data_pipeline.validators.data_validator import DataValidator
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from src.database.schemas import ExtractionResult
from src.config.settings import settings
from loguru import logger


def main():
    """Run the extraction pipeline on sample PDFs."""
    # Setup logging
    setup_logging()

    logger.info("=" * 80)
    logger.info("METADATA EXTRACTION PIPELINE (Simplified)")
    logger.info("=" * 80)

    # Check if LLM API key is configured
    if not settings.has_llm_key():
        logger.error("No LLM API key configured!")
        logger.error("Please set OPENAI_API_KEY in .env file")
        sys.exit(1)

    logger.info(f"Using LLM: {settings.extraction_model}")
    logger.info("")

    # Initialize components
    logger.info("Initializing components...")
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
    pdf_dir = Path("data/raw/sample_pdfs")
    if not pdf_dir.exists():
        logger.error(f"Directory not found: {pdf_dir}")
        logger.error("Please run scripts/download_simple.py first")
        sys.exit(1)

    pdf_files = list(pdf_dir.glob("*.pdf"))

    if not pdf_files:
        logger.error("No PDF files found")
        logger.error("Please run scripts/download_simple.py first")
        sys.exit(1)

    logger.info(f"Found {len(pdf_files)} PDF files")
    logger.info("")

    # Ask for confirmation
    logger.info(f"This will process {len(pdf_files)} cases using {settings.extraction_model}")
    logger.info(f"Estimated cost: ~${len(pdf_files) * 0.01:.2f}")
    logger.info("")

    # Process cases
    logger.info("=" * 80)
    logger.info("PROCESSING CASES")
    logger.info("=" * 80)

    extraction_results = []
    stats = {
        'total': len(pdf_files),
        'successful': 0,
        'failed': 0,
        'total_time': 0,
        'errors': []
    }

    for pdf_path in tqdm(pdf_files, desc="Processing cases"):
        try:
            start_time = time.time()

            # Extract text from PDF
            pdf_result = pdf_extractor.extract_text(pdf_path)

            if not pdf_result["success"]:
                raise Exception(f"PDF extraction failed: {pdf_result.get('error')}")

            full_text = pdf_result["text"]
            page_count = pdf_result["page_count"]

            # Extract metadata using LLM
            metadata = metadata_extractor.extract_case_metadata(
                judgment_text=full_text,
                case_id=pdf_path.stem
            )

            # Validate
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
                page_count=page_count
            )

            extraction_results.append(result)
            stats['successful'] += 1
            stats['total_time'] += extraction_time

        except Exception as e:
            stats['failed'] += 1
            stats['errors'].append({
                'file': pdf_path.name,
                'error': str(e)
            })
            logger.error(f"Failed to process {pdf_path.name}: {e}")

    # Load to database
    logger.info("")
    logger.info("=" * 80)
    logger.info("LOADING TO DATABASE")
    logger.info("=" * 80)

    loading_stats = db_loader.load_batch(extraction_results)

    # Get LLM statistics
    llm_stats = metadata_extractor.llm_client.get_stats()

    # Print summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("EXTRACTION SUMMARY")
    logger.info("=" * 80)

    logger.info(f"Processing:")
    logger.info(f"  Total cases: {stats['total']}")
    logger.info(f"  Successful: {stats['successful']}")
    logger.info(f"  Failed: {stats['failed']}")
    logger.info(f"  Success rate: {stats['successful'] / stats['total'] * 100:.1f}%")
    logger.info("")

    if stats['successful'] > 0:
        avg_confidence = sum(r.metadata.get_average_confidence() for r in extraction_results) / len(extraction_results)
        logger.info(f"Quality:")
        logger.info(f"  Average confidence: {avg_confidence:.2f}")
        logger.info("")

    logger.info(f"LLM Usage:")
    logger.info(f"  Provider: {llm_stats['provider']}")
    logger.info(f"  Model: {llm_stats['model']}")
    logger.info(f"  Total requests: {llm_stats['total_requests']}")
    logger.info(f"  Total tokens: {llm_stats['total_tokens']:,}")
    logger.info(f"  Estimated cost: ${llm_stats['estimated_cost']:.4f}")
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
    logger.info("")

    # Show errors if any
    if stats['errors']:
        logger.warning(f"Extraction errors ({len(stats['errors'])}):")
        for err in stats['errors'][:5]:
            logger.warning(f"  {err['file']}: {err['error']}")

    logger.info("")
    logger.info("✅ Extraction pipeline complete!")
    logger.info("")
    logger.info("Next step: Run 'python scripts/04_validate_quality.py' to review quality")

    # Save results to JSON for inspection
    results_file = Path("data/processed/extraction_results.json")
    results_file.parent.mkdir(parents=True, exist_ok=True)

    with open(results_file, 'w') as f:
        json.dump({
            'stats': stats,
            'llm_stats': llm_stats,
            'loading_stats': loading_stats,
            'db_stats': db_stats
        }, f, indent=2)

    logger.info(f"Results saved to: {results_file}")


if __name__ == "__main__":
    main()
