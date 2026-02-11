#!/usr/bin/env python3
"""
Script to validate and review extraction quality.
Shows cases with low confidence, validation errors, and suggests improvements.
"""
import sys
from pathlib import Path
from collections import Counter

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_logging
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from loguru import logger


def print_case_summary(case, index: int):
    """Print a summary of a case."""
    logger.info(f"\n{index}. Case ID: {case.case_id or 'N/A'}")
    logger.info(f"   Title: {case.case_title[:80] if case.case_title else 'N/A'}...")
    logger.info(f"   Court: {case.court or 'N/A'}")
    logger.info(f"   Date: {case.date_of_judgment or 'N/A'}")
    logger.info(f"   Type: {case.case_type or 'N/A'}")
    logger.info(f"   Verdict: {case.verdict or 'N/A'}")
    logger.info(f"   Avg Confidence: {case.average_confidence:.2f}" if case.average_confidence else "   Avg Confidence: N/A")
    logger.info(f"   Validation Status: {case.validation_status}")

    if case.confidence_scores:
        low_conf = {k: v for k, v in case.confidence_scores.items() if v < 0.7}
        if low_conf:
            logger.info(f"   Low confidence fields: {low_conf}")

    if case.validation_errors:
        logger.info(f"   Errors: {', '.join(case.validation_errors[:3])}")

    if case.validation_warnings:
        logger.info(f"   Warnings: {', '.join(case.validation_warnings[:3])}")


def main():
    """Validate extraction quality."""
    # Setup logging
    setup_logging()

    logger.info("=" * 80)
    logger.info("EXTRACTION QUALITY VALIDATION")
    logger.info("=" * 80)

    # Initialize database loader
    db_loader = DatabaseLoader()

    # Get database statistics
    logger.info("Fetching database statistics...")
    db_stats = db_loader.get_database_stats()

    logger.info("")
    logger.info("DATABASE OVERVIEW")
    logger.info("-" * 80)
    logger.info(f"Total cases: {db_stats['total_cases']}")
    logger.info(f"Valid cases: {db_stats['valid_cases']} ({db_stats['valid_cases'] / db_stats['total_cases'] * 100:.1f}%)")
    logger.info(f"Needs review: {db_stats['needs_review']} ({db_stats['needs_review'] / db_stats['total_cases'] * 100:.1f}%)")
    logger.info(f"Invalid cases: {db_stats['invalid_cases']} ({db_stats['invalid_cases'] / db_stats['total_cases'] * 100:.1f}%)")
    logger.info(f"Average confidence: {db_stats['average_confidence']:.2f}")
    logger.info(f"Total statutes referenced: {db_stats['total_statutes']}")
    logger.info(f"Total precedents cited: {db_stats['total_precedents']}")

    # Get cases that need review
    logger.info("")
    logger.info("=" * 80)
    logger.info("CASES NEEDING REVIEW")
    logger.info("=" * 80)

    needs_review = db_loader.get_cases_by_validation_status("needs_review", limit=10)

    if needs_review:
        logger.info(f"Found {len(needs_review)} cases needing review (showing first 10):")

        for i, case in enumerate(needs_review, 1):
            print_case_summary(case, i)

        # Analyze common warnings
        all_warnings = []
        for case in needs_review:
            if case.validation_warnings:
                all_warnings.extend(case.validation_warnings)

        if all_warnings:
            warning_counts = Counter(all_warnings)
            logger.info("")
            logger.info("Most common warnings:")
            for warning, count in warning_counts.most_common(5):
                logger.info(f"  {count}x: {warning}")
    else:
        logger.info("No cases need review!")

    # Get invalid cases
    logger.info("")
    logger.info("=" * 80)
    logger.info("INVALID CASES")
    logger.info("=" * 80)

    invalid_cases = db_loader.get_cases_by_validation_status("invalid", limit=10)

    if invalid_cases:
        logger.info(f"Found {len(invalid_cases)} invalid cases (showing first 10):")

        for i, case in enumerate(invalid_cases, 1):
            print_case_summary(case, i)

        # Analyze common errors
        all_errors = []
        for case in invalid_cases:
            if case.validation_errors:
                all_errors.extend(case.validation_errors)

        if all_errors:
            error_counts = Counter(all_errors)
            logger.info("")
            logger.info("Most common errors:")
            for error, count in error_counts.most_common(5):
                logger.info(f"  {count}x: {error}")
    else:
        logger.info("No invalid cases!")

    # Get low confidence cases
    logger.info("")
    logger.info("=" * 80)
    logger.info("LOW CONFIDENCE CASES")
    logger.info("=" * 80)

    # Fetch cases with low average confidence
    session = db_loader.SessionLocal()
    try:
        from src.database.models import Case
        low_conf_cases = session.query(Case).filter(
            Case.average_confidence < 0.6
        ).limit(10).all()

        if low_conf_cases:
            logger.info(f"Found {len(low_conf_cases)} cases with confidence < 0.6 (showing first 10):")

            for i, case in enumerate(low_conf_cases, 1):
                print_case_summary(case, i)
        else:
            logger.info("No low confidence cases!")

    finally:
        session.close()

    # Field-level analysis
    logger.info("")
    logger.info("=" * 80)
    logger.info("FIELD-LEVEL COMPLETENESS")
    logger.info("=" * 80)

    session = db_loader.SessionLocal()
    try:
        from src.database.models import Case
        from sqlalchemy import func

        all_cases = session.query(Case).all()

        if all_cases:
            field_stats = {
                "case_title": sum(1 for c in all_cases if c.case_title),
                "court": sum(1 for c in all_cases if c.court),
                "date_of_judgment": sum(1 for c in all_cases if c.date_of_judgment),
                "case_type": sum(1 for c in all_cases if c.case_type),
                "verdict": sum(1 for c in all_cases if c.verdict),
                "bench": sum(1 for c in all_cases if c.bench),
                "petitioner": sum(1 for c in all_cases if c.petitioner),
                "respondent": sum(1 for c in all_cases if c.respondent),
                "statutes_cited": sum(1 for c in all_cases if c.sections_invoked),
                "key_arguments": sum(1 for c in all_cases if c.key_arguments_petitioner or c.key_arguments_respondent),
                "court_reasoning": sum(1 for c in all_cases if c.court_reasoning),
            }

            total = len(all_cases)
            logger.info(f"Field completeness across {total} cases:")
            for field, count in sorted(field_stats.items(), key=lambda x: x[1], reverse=True):
                percentage = count / total * 100
                logger.info(f"  {field}: {count}/{total} ({percentage:.1f}%)")

    finally:
        session.close()

    # Recommendations
    logger.info("")
    logger.info("=" * 80)
    logger.info("RECOMMENDATIONS")
    logger.info("=" * 80)

    if db_stats['average_confidence'] < 0.7:
        logger.warning("⚠️  Average confidence is below 0.7")
        logger.warning("   Consider improving extraction prompts or using a more capable model")

    if db_stats['invalid_cases'] > db_stats['total_cases'] * 0.1:
        logger.warning(f"⚠️  More than 10% of cases are invalid")
        logger.warning("   Review common errors and adjust validation rules")

    if db_stats['valid_cases'] > db_stats['total_cases'] * 0.8:
        logger.info("✅ Extraction quality is good (>80% valid cases)")

    if db_stats['average_confidence'] >= 0.75:
        logger.info("✅ Average confidence is high (≥0.75)")

    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Review cases needing manual verification")
    logger.info("  2. Adjust extraction prompts based on common errors")
    logger.info("  3. Run notebooks/data_exploration.ipynb for detailed analysis")


if __name__ == "__main__":
    main()
