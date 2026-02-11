#!/usr/bin/env python3
"""
Extract metadata from diverse court PDFs using LLM.

Processes all PDFs downloaded by 08_download_diverse.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_pipeline.extractors.pdf_extractor import PDFExtractor
from src.data_pipeline.extractors.metadata_extractor import MetadataExtractor
from src.data_pipeline.validators.data_validator import DataValidator
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from loguru import logger
from tqdm import tqdm
import json

def main():
    logger.info("="*60)
    logger.info("DIVERSE CASES EXTRACTION")
    logger.info("="*60)

    # Find all PDFs in diverse_courts directory
    pdf_dir = Path('data/raw/diverse_courts')

    if not pdf_dir.exists():
        logger.error(f"Directory not found: {pdf_dir}")
        logger.error("Run 08_download_diverse.py first!")
        return

    pdf_files = list(pdf_dir.glob('**/*.pdf'))

    if not pdf_files:
        logger.error("No PDF files found!")
        return

    logger.info(f"Found {len(pdf_files)} PDF files to process")
    logger.info(f"Estimated cost: ${len(pdf_files) * 0.00035:.2f}")
    logger.info(f"Estimated time: ~{len(pdf_files) * 2.5 / 60:.0f} minutes")

    response = input("\nProceed with extraction? (yes/no): ")
    if response.lower() != 'yes':
        logger.warning("Extraction cancelled")
        return

    # Initialize components
    logger.info("Initializing components...")
    pdf_extractor = PDFExtractor()
    metadata_extractor = MetadataExtractor()
    validator = DataValidator()
    db_loader = DatabaseLoader()

    # Initialize database
    db_loader.init_db()

    # Statistics
    stats = {
        'total': len(pdf_files),
        'successful': 0,
        'failed': 0,
        'duplicates': 0,
        'errors': [],
    }

    # Process each PDF
    logger.info("\nProcessing cases...")

    for pdf_path in tqdm(pdf_files, desc="Extracting metadata"):
        try:
            # Extract text from PDF
            pdf_result = pdf_extractor.extract_text(pdf_path)

            if not pdf_result or not pdf_result.get('text'):
                logger.warning(f"No text extracted from {pdf_path.name}")
                stats['failed'] += 1
                stats['errors'].append(f"{pdf_path.name}: No text extracted")
                continue

            full_text = pdf_result['text']
            case_id = pdf_path.stem

            # Extract metadata with LLM
            metadata = metadata_extractor.extract_case_metadata(full_text, case_id=case_id)

            if not metadata:
                logger.warning(f"No metadata extracted from {pdf_path.name}")
                stats['failed'] += 1
                stats['errors'].append(f"{pdf_path.name}: No metadata extracted")
                continue

            # Validate metadata
            validation_result = validator.validate(metadata)

            # Load to database
            try:
                case_obj = db_loader.load_case(
                    metadata=metadata,
                    full_text=full_text,
                    validation=validation_result,
                    extraction_model=metadata_extractor.llm_client.model,
                    source_file=str(pdf_path),
                    page_count=pdf_result.get('page_count')
                )

                if case_obj:
                    stats['successful'] += 1
                else:
                    stats['duplicates'] += 1

            except Exception as e:
                logger.error(f"Error loading case {case_id}: {e}")
                stats['failed'] += 1
                stats['errors'].append(f"{pdf_path.name}: Database load error: {e}")

        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {e}")
            stats['failed'] += 1
            stats['errors'].append(f"{pdf_path.name}: {e}")

    # Print summary
    logger.success(f"\n{'='*60}")
    logger.success(f"EXTRACTION COMPLETE")
    logger.success(f"{'='*60}")
    logger.info(f"Total processed: {stats['total']}")
    logger.success(f"✓ Successful: {stats['successful']}")
    logger.info(f"Duplicates skipped: {stats['duplicates']}")
    logger.warning(f"✗ Failed: {stats['failed']}")

    if stats['errors']:
        logger.warning(f"\nFirst 10 errors:")
        for error in stats['errors'][:10]:
            logger.warning(f"  - {error}")

    # Save results
    results_file = Path('data/processed/diverse_extraction_results.json')
    with open(results_file, 'w') as f:
        json.dump(stats, f, indent=2)

    logger.info(f"\nResults saved to: {results_file}")

    # Print database stats
    logger.info("\nFinal database statistics:")
    db_stats = db_loader.get_database_stats()
    for key, value in db_stats.items():
        logger.info(f"  {key}: {value}")

if __name__ == "__main__":
    main()
