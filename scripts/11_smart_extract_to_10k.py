#!/usr/bin/env python3
"""
Smart extraction to reach exactly 10,000 cases.
Extracts from diverse courts PDFs until we hit 10,000 total.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.database.models import Case
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from src.data_pipeline.extractors.pdf_extractor import PDFExtractor
from src.data_pipeline.extractors.metadata_extractor import MetadataExtractor
from src.data_pipeline.validators.data_validator import DataValidator
from loguru import logger
from tqdm import tqdm
from sqlalchemy import func
import argparse

TARGET_CASES = 10000

def get_current_count():
    """Get current number of cases in database"""
    db = DatabaseLoader()
    session = db.SessionLocal()
    try:
        count = session.query(func.count(Case.id)).scalar()
        return count
    finally:
        session.close()

def get_unprocessed_pdfs():
    """Find PDFs that haven't been processed yet"""
    diverse_dir = Path("data/raw/diverse_courts")

    # Get all PDF files
    all_pdfs = list(diverse_dir.rglob("*.pdf"))
    logger.info(f"Found {len(all_pdfs)} total PDF files")

    # Get already processed filenames from database
    db = DatabaseLoader()
    session = db.SessionLocal()
    try:
        processed = session.query(Case.source_file_path).filter(Case.source_file_path.isnot(None)).all()
        processed_paths = {str(Path(p[0]).name) for p in processed if p[0]}
        logger.info(f"Already processed: {len(processed_paths)} files")
    finally:
        session.close()

    # Filter unprocessed
    unprocessed = [p for p in all_pdfs if p.name not in processed_paths]
    logger.info(f"Unprocessed PDFs: {len(unprocessed)}")

    return unprocessed

def extract_single_case(pdf_path, pdf_extractor, metadata_extractor, validator, db_loader):
    """Extract and load a single case"""
    try:
        # Extract text (returns a dict)
        extraction_result = pdf_extractor.extract_text(pdf_path)

        if not extraction_result or not extraction_result.get('success'):
            logger.warning(f"Failed to extract text from {pdf_path.name}")
            return False

        text = extraction_result.get('text', '')
        page_count = extraction_result.get('page_count', 0)

        if not text or len(text.strip()) < 100:
            logger.warning(f"Insufficient text extracted from {pdf_path.name}")
            return False

        # Extract metadata
        metadata = metadata_extractor.extract_case_metadata(text)
        if not metadata:
            logger.warning(f"Failed to extract metadata from {pdf_path.name}")
            return False

        # Validate
        validation = validator.validate(metadata)

        # Load to database with correct parameters
        case_id = db_loader.load_case(
            metadata=metadata,
            full_text=text,
            validation=validation,
            extraction_model="gpt-4o-mini",
            source_file=str(pdf_path),
            page_count=page_count
        )

        if case_id:
            logger.debug(f"✓ Loaded: {pdf_path.name} (ID: {case_id})")
            return True
        else:
            logger.warning(f"✗ Failed to load: {pdf_path.name}")
            return False

    except Exception as e:
        import traceback
        logger.error(f"Error processing {pdf_path.name}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Smart extraction to 10,000 cases')
    parser.add_argument('--target', type=int, default=TARGET_CASES, help='Target number of cases')
    args = parser.parse_args()

    logger.info("="*60)
    logger.info("SMART EXTRACTION TO 10,000 CASES")
    logger.info("="*60)

    # Check current count
    current_count = get_current_count()
    logger.info(f"Current cases in database: {current_count:,}")

    if current_count >= args.target:
        logger.success(f"Already have {current_count:,} cases (target: {args.target:,})")
        logger.success("Nothing to do!")
        return

    needed = args.target - current_count
    logger.info(f"Need to extract: {needed:,} more cases")

    # Get unprocessed PDFs
    unprocessed_pdfs = get_unprocessed_pdfs()

    if not unprocessed_pdfs:
        logger.warning("No unprocessed PDFs found!")
        return

    # We'll try to extract 'needed + buffer' to account for failures
    buffer = int(needed * 0.3)  # 30% buffer for failed extractions
    to_process = min(len(unprocessed_pdfs), needed + buffer)

    logger.info(f"Will process up to {to_process} PDFs (includes 30% failure buffer)")

    # Confirm
    response = input(f"\nProceed with extraction? (yes/no): ")
    if response.lower() != 'yes':
        logger.warning("Extraction cancelled")
        return

    # Initialize components
    logger.info("\nInitializing extraction components...")
    pdf_extractor = PDFExtractor()
    metadata_extractor = MetadataExtractor()
    validator = DataValidator()
    db_loader = DatabaseLoader()

    # Process PDFs
    logger.info("\nStarting extraction...\n")
    successful = 0
    failed = 0

    with tqdm(total=needed, desc="Extracting to 10K", unit="cases") as pbar:
        for pdf_path in unprocessed_pdfs[:to_process]:
            # Check if we've hit target
            current = get_current_count()
            if current >= args.target:
                logger.success(f"\n✓ Target reached! {current:,} cases")
                break

            # Process
            if extract_single_case(pdf_path, pdf_extractor, metadata_extractor, validator, db_loader):
                successful += 1
                pbar.update(1)
            else:
                failed += 1

            # Update progress bar description
            if (successful + failed) % 10 == 0:
                current = get_current_count()
                remaining = args.target - current
                pbar.set_description(f"Extracting to 10K ({remaining} remaining)")

    # Final report
    final_count = get_current_count()

    logger.info("\n" + "="*60)
    logger.success("EXTRACTION COMPLETE")
    logger.info("="*60)
    logger.info(f"Started with:        {current_count:,} cases")
    logger.info(f"Successfully added:  {successful:,} cases")
    logger.info(f"Failed:              {failed:,} cases")
    logger.info(f"Final count:         {final_count:,} cases")
    logger.info(f"Target:              {args.target:,} cases")

    if final_count >= args.target:
        logger.success(f"\n🎉 TARGET ACHIEVED! {final_count:,} cases")
    else:
        shortfall = args.target - final_count
        logger.warning(f"\n⚠️  Short by {shortfall:,} cases. May need more PDFs or retry failed ones.")

    # Cost estimate
    cost = successful * 0.00035
    logger.info(f"\nEstimated cost: ${cost:.2f}")

if __name__ == "__main__":
    main()
