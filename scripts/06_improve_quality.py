#!/usr/bin/env python3
"""
Improve data quality by re-extracting invalid and low-confidence cases.

Handles:
1. Invalid cases (472 cases missing critical fields)
2. Low-confidence cases (<60%, 1016 cases)

Uses enhanced prompts with explicit instructions to improve extraction quality.

Expected cost: ~$0.50 (1,488 cases × $0.00035)
Expected time: ~45-60 minutes
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.models import Case
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from src.data_pipeline.extractors.metadata_extractor import MetadataExtractor
from src.data_pipeline.validators.data_validator import DataValidator
from src.utils.llm_client import LLMClient
from loguru import logger
from tqdm import tqdm
import json
from typing import List, Tuple

def get_cases_needing_improvement(confidence_threshold: float = 0.6) -> Tuple[List[Case], List[Case]]:
    """Fetch invalid cases and low-confidence cases"""
    db = DatabaseLoader()
    session = db.SessionLocal()

    try:
        # Get invalid cases
        invalid_cases = (
            session.query(Case)
            .filter(Case.validation_status == 'invalid')
            .all()
        )

        # Get low-confidence cases (excluding already invalid)
        low_conf_cases = (
            session.query(Case)
            .filter(Case.average_confidence < confidence_threshold)
            .filter(Case.validation_status != 'invalid')
            .all()
        )

        logger.info(f"Found {len(invalid_cases)} invalid cases")
        logger.info(f"Found {len(low_conf_cases)} low-confidence cases (<{confidence_threshold})")

        return invalid_cases, low_conf_cases

    finally:
        session.close()

def improve_case(case: Case, metadata_extractor: MetadataExtractor, validator: DataValidator) -> dict:
    """
    Try to improve extraction quality for a single case.

    Returns dict with:
    - success: bool
    - old_confidence: float
    - new_confidence: float
    - old_status: str
    - new_status: str
    """

    if not case.full_text:
        logger.warning(f"Case {case.id} has no full_text, skipping")
        return {
            'success': False,
            'old_confidence': case.average_confidence or 0,
            'new_confidence': case.average_confidence or 0,
            'old_status': case.validation_status,
            'new_status': case.validation_status,
        }

    try:
        old_confidence = case.average_confidence or 0
        old_status = case.validation_status

        # Re-extract metadata
        logger.debug(f"Re-extracting case {case.id}: {(case.case_title or '')[:50]}...")

        new_metadata = metadata_extractor.extract_case_metadata(
            case.full_text,
            case_id=str(case.id)
        )

        if not new_metadata:
            logger.warning(f"Re-extraction returned no metadata for case {case.id}")
            return {
                'success': False,
                'old_confidence': old_confidence,
                'new_confidence': old_confidence,
                'old_status': old_status,
                'new_status': old_status,
            }

        # Validate new extraction
        validation_result = validator.validate(new_metadata)

        new_confidence = new_metadata.average_confidence or 0
        new_status = validation_result.status

        # Check if extraction improved
        improved = False

        if old_status == 'invalid' and new_status != 'invalid':
            # Recovered from invalid status
            improved = True
            logger.success(f"✓ Recovered case {case.id}: invalid → {new_status}")

        elif new_confidence > old_confidence + 0.05:
            # Confidence improved by at least 5%
            improved = True
            logger.info(f"✓ Boosted case {case.id}: {old_confidence:.2f} → {new_confidence:.2f}")

        if improved:
            # Update case with new data
            update_case_from_metadata(case, new_metadata, validation_result)

        return {
            'success': improved,
            'old_confidence': old_confidence,
            'new_confidence': new_confidence,
            'old_status': old_status,
            'new_status': new_status,
        }

    except Exception as e:
        logger.error(f"Error improving case {case.id}: {e}")
        return {
            'success': False,
            'old_confidence': case.average_confidence or 0,
            'new_confidence': case.average_confidence or 0,
            'old_status': case.validation_status,
            'new_status': case.validation_status,
        }

def update_case_from_metadata(case: Case, metadata, validation_result):
    """Update case object with new metadata"""

    # Update all fields from metadata
    case.case_title = metadata.case_title
    case.court = metadata.court
    case.bench = metadata.bench
    case.date_of_judgment = metadata.date_of_judgment
    case.case_type = metadata.case_type
    case.petitioner = metadata.petitioner
    case.respondent = metadata.respondent
    case.statutes_cited = metadata.statutes_cited
    case.sections_invoked = metadata.sections_invoked
    case.charges = metadata.charges
    case.verdict = metadata.verdict
    case.sentence = metadata.sentence
    case.key_arguments_petitioner = metadata.key_arguments_petitioner
    case.key_arguments_respondent = metadata.key_arguments_respondent
    case.court_reasoning = metadata.court_reasoning
    case.headnotes = metadata.headnotes

    # Update validation fields
    case.average_confidence = metadata.average_confidence
    case.confidence_scores = metadata.confidence_scores
    case.validation_status = validation_result.status
    case.validation_errors = json.dumps(validation_result.errors) if validation_result.errors else None
    case.validation_warnings = json.dumps(validation_result.warnings) if validation_result.warnings else None

def main():
    logger.info("="*60)
    logger.info("DATA QUALITY IMPROVEMENT")
    logger.info("="*60)

    # Get cases needing improvement
    invalid_cases, low_conf_cases = get_cases_needing_improvement(confidence_threshold=0.6)

    total_cases = len(invalid_cases) + len(low_conf_cases)

    if total_cases == 0:
        logger.info("No cases need improvement!")
        return

    logger.info(f"\nTotal cases to process: {total_cases}")
    logger.info(f"  - Invalid cases: {len(invalid_cases)}")
    logger.info(f"  - Low-confidence cases: {len(low_conf_cases)}")
    logger.info(f"\nEstimated cost: ~${total_cases * 0.00035:.2f}")
    logger.info(f"Estimated time: ~{total_cases * 2.5 / 60:.0f} minutes")

    response = input("\nProceed? (yes/no): ")
    if response.lower() != 'yes':
        logger.warning("Quality improvement cancelled")
        return

    # Initialize components
    metadata_extractor = MetadataExtractor()
    validator = DataValidator()
    db = DatabaseLoader()

    # Combine all cases to process
    all_cases = invalid_cases + low_conf_cases

    # Statistics
    stats = {
        'total_processed': 0,
        'improved': 0,
        'unchanged': 0,
        'recovered_from_invalid': 0,
        'confidence_boosted': 0,
        'failed': 0,
    }

    # Process with progress bar
    session = db.SessionLocal()

    try:
        logger.info("\nProcessing cases...")

        for case in tqdm(all_cases, desc="Improving cases"):
            result = improve_case(case, metadata_extractor, validator)

            stats['total_processed'] += 1

            if result['success']:
                stats['improved'] += 1

                if result['old_status'] == 'invalid' and result['new_status'] != 'invalid':
                    stats['recovered_from_invalid'] += 1

                if result['new_confidence'] > result['old_confidence'] + 0.05:
                    stats['confidence_boosted'] += 1
            else:
                if result['old_confidence'] == result['new_confidence']:
                    stats['unchanged'] += 1
                else:
                    stats['failed'] += 1

            # Commit every 20 cases
            if stats['total_processed'] % 20 == 0:
                session.commit()
                logger.debug(f"Progress: {stats['total_processed']}/{total_cases} processed, {stats['improved']} improved")

        # Final commit
        session.commit()

        # Print summary
        logger.success(f"\n{'='*60}")
        logger.success(f"QUALITY IMPROVEMENT COMPLETE")
        logger.success(f"{'='*60}")
        logger.info(f"Total processed: {stats['total_processed']}")
        logger.success(f"✓ Improved: {stats['improved']} ({stats['improved']/stats['total_processed']*100:.1f}%)")
        logger.info(f"  - Recovered from invalid: {stats['recovered_from_invalid']}")
        logger.info(f"  - Confidence boosted: {stats['confidence_boosted']}")
        logger.info(f"Unchanged: {stats['unchanged']}")
        logger.info(f"Failed: {stats['failed']}")

        # Show new stats
        logger.info("\nNew database statistics:")
        total_cases_db = session.query(Case).count()
        invalid_count = session.query(Case).filter(Case.validation_status == 'invalid').count()
        low_conf_count = session.query(Case).filter(Case.average_confidence < 0.6).count()
        avg_conf = session.query(func.avg(Case.average_confidence)).scalar()

        logger.info(f"  Total cases: {total_cases_db}")
        logger.info(f"  Invalid: {invalid_count} ({invalid_count/total_cases_db*100:.1f}%)")
        logger.info(f"  Low confidence (<60%): {low_conf_count} ({low_conf_count/total_cases_db*100:.1f}%)")
        logger.info(f"  Average confidence: {avg_conf:.2%}")

    except Exception as e:
        session.rollback()
        logger.error(f"Error during quality improvement: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    from sqlalchemy import func
    main()
