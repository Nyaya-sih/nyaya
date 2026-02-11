#!/usr/bin/env python3
"""
Final court name standardization pass.
Cleans up any remaining variations to canonical forms.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.database.models import Case
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from loguru import logger
from sqlalchemy import func

# Comprehensive court name mappings
COURT_STANDARDIZATION = {
    # Bombay High Court variations
    "HIGH COURT OF JUDICATURE AT BOMBAY": "High Court of Bombay",
    "BOMBAY HIGH COURT": "High Court of Bombay",
    "Bombay High court": "High Court of Bombay",
    "High Court at Bombay": "High Court of Bombay",

    # Delhi High Court variations
    "HIGH COURT OF DELHI": "High Court of Delhi",
    "DELHI HIGH COURT": "High Court of Delhi",
    "Delhi High court": "High Court of Delhi",
    "High Court at Delhi": "High Court of Delhi",

    # Patna High Court variations (catch any remaining)
    "HIGH COURT OF JUDICATURE AT PATNA": "High Court of Patna",
    "PATNA HIGH COURT": "High Court of Patna",
    "Patna High court": "High Court of Patna",
    "High Court at Patna": "High Court of Patna",

    # Sikkim High Court variations
    "SIKKIM HIGH COURT": "High Court of Sikkim",
    "HIGH COURT OF SIKKIM": "High Court of Sikkim",
    "Sikkim High court": "High Court of Sikkim",

    # Manipur High Court variations
    "MANIPUR HIGH COURT": "High Court of Manipur",
    "HIGH COURT OF MANIPUR": "High Court of Manipur",
    "Manipur High court": "High Court of Manipur",

    # Tripura High Court variations
    "TRIPURA HIGH COURT": "High Court of Tripura",
    "HIGH COURT OF TRIPURA": "High Court of Tripura",
    "Tripura High court": "High Court of Tripura",

    # Gauhati High Court variations
    "GAUHATI HIGH COURT": "High Court of Gauhati",
    "HIGH COURT OF GAUHATI": "High Court of Gauhati",
    "Gauhati High court": "High Court of Gauhati",
    "Guwahati High Court": "High Court of Gauhati",

    # Karnataka High Court variations
    "KARNATAKA HIGH COURT": "High Court of Karnataka",
    "HIGH COURT OF KARNATAKA": "High Court of Karnataka",
    "Karnataka High court": "High Court of Karnataka",
    "High Court at Karnataka": "High Court of Karnataka",

    # Andhra Pradesh High Court variations
    "ANDHRA PRADESH HIGH COURT": "High Court of Andhra Pradesh",
    "HIGH COURT OF ANDHRA PRADESH": "High Court of Andhra Pradesh",
    "Andhra Pradesh High court": "High Court of Andhra Pradesh",

    # Jammu & Kashmir High Court variations
    "HIGH COURT OF JAMMU AND KASHMIR": "High Court of Jammu & Kashmir and Ladakh",
    "JAMMU AND KASHMIR HIGH COURT": "High Court of Jammu & Kashmir and Ladakh",
    "Jammu and Kashmir High Court": "High Court of Jammu & Kashmir and Ladakh",
    "J&K High Court": "High Court of Jammu & Kashmir and Ladakh",

    # Fix any null variations
    "null": None,
    "NULL": None,
    "": None,
}

def analyze_current_courts():
    """Show all unique court names and their counts"""
    db = DatabaseLoader()
    session = db.SessionLocal()

    try:
        court_counts = (
            session.query(Case.court, func.count(Case.id))
            .group_by(Case.court)
            .order_by(func.count(Case.id).desc())
            .all()
        )

        logger.info(f"\n{'='*80}")
        logger.info("CURRENT COURT NAME DISTRIBUTION")
        logger.info(f"{'='*80}")

        for court, count in court_counts:
            court_name = court if court else "NULL/Unknown"
            logger.info(f"{court_name:<60} {count:>6,} cases")

        logger.info(f"{'='*80}")
        logger.info(f"Total unique court names: {len(court_counts)}")

        return court_counts

    finally:
        session.close()

def standardize_court_names():
    """Update all court names to canonical forms"""
    db = DatabaseLoader()
    session = db.SessionLocal()

    total_updated = 0

    try:
        logger.info("\nStarting court name standardization...")

        for old_name, new_name in COURT_STANDARDIZATION.items():
            # Count how many cases will be updated
            count = session.query(Case).filter(Case.court == old_name).count()

            if count > 0:
                # Update cases
                session.query(Case).filter(Case.court == old_name).update(
                    {Case.court: new_name},
                    synchronize_session=False
                )

                if new_name:
                    logger.info(f"✓ Updated {count:,} cases: '{old_name}' → '{new_name}'")
                else:
                    logger.info(f"✓ Cleared {count:,} cases: '{old_name}' → NULL")
                total_updated += count

        session.commit()
        logger.success(f"\nTotal cases updated: {total_updated:,}")

    except Exception as e:
        session.rollback()
        logger.error(f"Error during standardization: {e}")
        raise
    finally:
        session.close()

def main():
    logger.info("="*80)
    logger.info("FINAL COURT NAME STANDARDIZATION")
    logger.info("="*80)

    # Show current state
    logger.info("\nCurrent court names:")
    analyze_current_courts()

    # Standardize
    logger.info(f"\nStandardizing {len(COURT_STANDARDIZATION)} variations...")
    standardize_court_names()

    # Show new state
    logger.info("\nFinal court distribution:")
    analyze_current_courts()

    logger.success("\n✅ Court name standardization complete!")

if __name__ == "__main__":
    main()
