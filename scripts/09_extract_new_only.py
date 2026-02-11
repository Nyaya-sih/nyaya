#!/usr/bin/env python3
"""
Extract metadata only from NEW diverse cases (skip already processed ones).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_pipeline.extractors.pdf_extractor import PDFExtractor
from src.data_pipeline.extractors.metadata_extractor import MetadataExtractor
from src.data_pipeline.validators.data_validator import DataValidator
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from src.database.models import Case
from loguru import logger
from tqdm import tqdm

def main():
    logger.info("="*60)
    logger.info("EXTRACT NEW DIVERSE CASES ONLY")
    logger.info("="*60)

    # Find all PDFs
    pdf_dir = Path('data/raw/diverse_courts')
    if not pdf_dir.exists():
        logger.error(f"Directory not found: {pdf_dir}")
        return

    all_pdfs = list(pdf_dir.glob('**/*.pdf'))
    logger.info(f"Found {len(all_pdfs)} total PDF files")

    # Get already processed files from database
    db = DatabaseLoader()
    session = db.SessionLocal()
    
    try:
        processed_paths = set(
            session.query(Case.source_file_path)
            .filter(Case.source_file_path.isnot(None))
            .all()
        )
        processed_paths = {str(p[0]) for p in processed_paths}
        logger.info(f"Already processed: {len(processed_paths)} files")
        
    finally:
        session.close()

    # Filter to only new PDFs
    new_pdfs = [
        pdf for pdf in all_pdfs 
        if str(pdf) not in processed_paths
    ]

    logger.info(f"New PDFs to extract: {len(new_pdfs)}")
    
    if not new_pdfs:
        logger.success("No new PDFs to process!")
        return

    logger.info(f"Estimated cost: ${len(new_pdfs) * 0.00035:.2f}")
    logger.info(f"Estimated time: ~{len(new_pdfs) * 12 / 60:.0f} minutes")

    # Initialize components
    logger.info("Initializing components...")
    pdf_extractor = PDFExtractor()
    metadata_extractor = MetadataExtractor()
    validator = DataValidator()
    db_loader = DatabaseLoader()
    db_loader.init_db()

    # Statistics
    stats = {
        'total': len(new_pdfs),
        'successful': 0,
        'failed': 0,
        'duplicates': 0,
        'errors': [],
    }

    # Process each new PDF
    logger.info("\nProcessing new cases...")

    for pdf_path in tqdm(new_pdfs, desc="Extracting metadata"):
        try:
            # Extract text
            pdf_result = pdf_extractor.extract_text(pdf_path)
            if not pdf_result or not pdf_result.get('text'):
                stats['failed'] += 1
                stats['errors'].append(f"{pdf_path.name}: No text")
                continue

            full_text = pdf_result['text']
            case_id = pdf_path.stem

            # Extract metadata
            metadata = metadata_extractor.extract_case_metadata(full_text, case_id=case_id)
            if not metadata:
                stats['failed'] += 1
                stats['errors'].append(f"{pdf_path.name}: No metadata")
                continue

            # Validate
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
                logger.error(f"Error loading {case_id}: {e}")
                stats['failed'] += 1
                stats['errors'].append(f"{pdf_path.name}: DB error: {e}")

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

    if stats['errors'] and len(stats['errors']) <= 20:
        logger.warning(f"\nErrors:")
        for error in stats['errors'][:20]:
            logger.warning(f"  {error}")

if __name__ == "__main__":
    main()
