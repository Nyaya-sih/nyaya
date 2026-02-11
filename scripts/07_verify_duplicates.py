#!/usr/bin/env python3
"""
Verify that duplicate cases were correctly identified and removed.
Find any remaining duplicates based on multiple criteria.

Duplicate detection strategies:
1. Exact match: same case_title + court + date
2. Case ID match: same case_id field (if present)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.models import Case
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from loguru import logger
from collections import defaultdict
from datetime import datetime

def find_exact_duplicates():
    """Find cases with identical case_title + court + date"""
    db = DatabaseLoader()
    session = db.SessionLocal()

    try:
        # Get all cases
        cases = session.query(Case).all()

        # Group by case_title, court, date_of_judgment
        groups = defaultdict(list)
        for case in cases:
            key = (
                case.case_title.strip().lower() if case.case_title else "",
                case.court.strip().lower() if case.court else "",
                str(case.date_of_judgment) if case.date_of_judgment else ""
            )
            groups[key].append(case)

        # Find groups with >1 case
        duplicates = {k: v for k, v in groups.items() if len(v) > 1}

        logger.info(f"Found {len(duplicates)} exact duplicate groups")

        if duplicates:
            logger.warning(f"\n{'='*60}")
            logger.warning("DUPLICATE GROUPS FOUND")
            logger.warning(f"{'='*60}\n")

            for key, cases in duplicates.items():
                logger.warning(f"Duplicate group ({len(cases)} cases):")
                logger.warning(f"  Title: {key[0][:60]}")
                logger.warning(f"  Court: {key[1]}")
                logger.warning(f"  Date: {key[2]}")
                for case in cases:
                    conf = case.average_confidence or 0
                    logger.warning(f"    - ID: {case.id}, Confidence: {conf:.2f}")
                logger.warning("")

        return duplicates

    finally:
        session.close()

def remove_duplicates(duplicates, keep='highest_confidence'):
    """
    Remove duplicate cases, keeping either:
    - highest_confidence: Keep case with highest average_confidence
    - newest: Keep most recently added case
    """
    db = DatabaseLoader()
    session = db.SessionLocal()

    removed_count = 0
    kept_ids = []
    removed_ids = []

    try:
        for key, cases in duplicates.items():
            if keep == 'highest_confidence':
                # Keep case with highest confidence
                cases_sorted = sorted(cases, key=lambda c: c.average_confidence or 0, reverse=True)
            else:  # newest
                cases_sorted = sorted(cases, key=lambda c: c.id, reverse=True)

            keep_case = cases_sorted[0]
            remove_cases = cases_sorted[1:]

            kept_ids.append(keep_case.id)

            for case in remove_cases:
                logger.info(f"Removing duplicate case ID {case.id} (keeping ID {keep_case.id})")
                session.delete(case)
                removed_ids.append(case.id)
                removed_count += 1

        session.commit()
        logger.success(f"✓ Removed {removed_count} duplicate cases")
        logger.success(f"✓ Kept {len(kept_ids)} unique cases")

        return removed_count, kept_ids, removed_ids

    except Exception as e:
        session.rollback()
        logger.error(f"Error removing duplicates: {e}")
        raise
    finally:
        session.close()

def main():
    logger.info("="*60)
    logger.info("DUPLICATE VERIFICATION")
    logger.info("="*60)

    # Find exact duplicates
    logger.info("\nSearching for exact duplicates...")
    logger.info("(Same case_title + court + date_of_judgment)")

    exact_dups = find_exact_duplicates()

    if not exact_dups:
        logger.success("\n✅ No duplicates found! Database is clean.")
        return

    total_duplicate_cases = sum(len(cases) - 1 for cases in exact_dups.values())

    logger.warning(f"\nFound {len(exact_dups)} duplicate groups")
    logger.warning(f"Total duplicate cases to remove: {total_duplicate_cases}")

    response = input("\nRemove duplicates (keeping highest confidence)? (yes/no): ")

    if response.lower() == 'yes':
        removed_count, kept_ids, removed_ids = remove_duplicates(exact_dups, keep='highest_confidence')

        logger.success(f"\n{'='*60}")
        logger.success(f"DUPLICATE REMOVAL COMPLETE")
        logger.success(f"{'='*60}")
        logger.success(f"Removed: {removed_count} cases")
        logger.success(f"Kept: {len(kept_ids)} cases")

        # Save report
        report = {
            'removed_count': removed_count,
            'kept_ids': kept_ids,
            'removed_ids': removed_ids,
            'timestamp': datetime.now().isoformat(),
        }

        import json
        with open('data/processed/duplicate_removal_report.json', 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"\nReport saved to: data/processed/duplicate_removal_report.json")
    else:
        logger.warning("Duplicate removal cancelled")

if __name__ == "__main__":
    main()
