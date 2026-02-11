#!/usr/bin/env python3
"""
Standardize court names in the database to canonical forms.

Current problem: Same courts have multiple name variations
- "HIGH COURT OF JUDICATURE AT PATNA"
- "Patna High Court"
- "HIGH COURT PATNA"

These should all be: "High Court of Patna"
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.models import Case
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from loguru import logger
from sqlalchemy import func

# Canonical court name mappings
COURT_STANDARDIZATION = {
    # Patna High Court variations
    "HIGH COURT OF JUDICATURE AT PATNA": "High Court of Patna",
    "High Court of Judicature at Patna": "High Court of Patna",
    "Patna High Court": "High Court of Patna",
    "HIGH COURT PATNA": "High Court of Patna",
    "High Court at Patna": "High Court of Patna",
    "PATNA HIGH COURT": "High Court of Patna",
    "Patna High court": "High Court of Patna",

    # Sikkim High Court variations
    "HIGH COURT OF SIKKIM": "High Court of Sikkim",
    "High Court of Sikkim": "High Court of Sikkim",
    "SIKKIM HIGH COURT": "High Court of Sikkim",
    "Sikkim High court": "High Court of Sikkim",
    "HIGH COURT OF SIKKIM : GANGTOK": "High Court of Sikkim",
    "THE HIGH COURT OF SIKKIM : GANGTOK": "High Court of Sikkim",
    "HIGH COURT OF SIKKIM, GANGTOK": "High Court of Sikkim",
    "THE HIGH COURT OF SIKKIM": "High Court of Sikkim",
    "THE HIGH COURT OF SIKKIM: GANGTOK": "High Court of Sikkim",
    "HIGH COURT OF SIKKIM AT GANGTOK": "High Court of Sikkim",
    "THE HIGH COURT OF SIKKIM AT GANGTOK": "High Court of Sikkim",
    "High Court of Sikkim at Gangtok": "High Court of Sikkim",
    "HI GH COURT OF SI KKI M : GANGTOK": "High Court of Sikkim",

    # Manipur High Court variations
    "HIGH COURT OF MANIPUR": "High Court of Manipur",
    "Manipur High Court": "High Court of Manipur",
    "MANIPUR HIGH COURT": "High Court of Manipur",
    "HIGH COURT OF MANIPUR AT IMPHAL": "High Court of Manipur",
    "High Court of Manipur": "High Court of Manipur",

    # Tripura High Court variations
    "HIGH COURT OF TRIPURA": "High Court of Tripura",
    "Tripura High Court": "High Court of Tripura",
    "TRIPURA HIGH COURT": "High Court of Tripura",

    # Bombay High Court variations
    "HIGH COURT OF JUDICATURE AT BOMBAY": "High Court of Bombay",
    "HIGH COURT OF JUDICATURE OF BOMBAY": "High Court of Bombay",
    "HIGH COURT OF JUDICATURE AT BOMBAY, BENCH AT AURANGABAD": "High Court of Bombay",
    "HIGH COURT OF JUDICATURE AT BOMBAY BENCH AT AURANGABAD": "High Court of Bombay",
    "HIGH COURT OF JUDICATURE OF BOMBAY, BENCH AT AURANGABAD": "High Court of Bombay",
    "High Court of Judicature at Bombay, Bench at Aurangabad": "High Court of Bombay",
    "High Court of Judicature of Bombay, Bench at Aurangabad": "High Court of Bombay",
    "HIGH COURT AT BOMBAY": "High Court of Bombay",
    "High Court of Judicature at Bombay": "High Court of Bombay",
    "BOMBAY HIGH COURT": "High Court of Bombay",
    "Bombay High Court": "High Court of Bombay",

    # Gauhati High Court variations
    "GAUHATI HIGH COURT": "High Court of Gauhati",
    "GAUHATI HIGH COURT (HIGH COURT OF ASSAM, NAGALAND, MIZORAM AND ARUNACHAL PRADESH) (ITANAGAR BENCH)": "High Court of Gauhati",
    "GAUHATI HIGH COURT (HIGH COURT OF ASSAM, NAGALAND, MIZORAM AND ARUNACHAL PRADESH)": "High Court of Gauhati",
    "Gauhati High Court": "High Court of Gauhati",

    # Karnataka High Court variations
    "HIGH COURT OF KARNATAKA": "High Court of Karnataka",
    "HIGH COURT OF KARNATAKA, DHARWAD BENCH": "High Court of Karnataka",
    "HIGH COURT OF KARNATAKA, DHARWAD": "High Court of Karnataka",
    "HIGH COURT OF KARNATAKA DHARWAD BENCH": "High Court of Karnataka",
    "HIGH COURT OF KARNATAKA - DHARWAD BENCH": "High Court of Karnataka",
    "HIGH COURT OF KARNATAKA AT BANGALORE": "High Court of Karnataka",
    "High Court of Karnataka, Dharwad": "High Court of Karnataka",
    "High Court of Karnataka, Dharwad Bench": "High Court of Karnataka",
    "High Court of Karnataka": "High Court of Karnataka",
    "Karnataka High Court": "High Court of Karnataka",

    # Delhi High Court variations
    "HIGH COURT OF DELHI": "High Court of Delhi",
    "DELHI HIGH COURT": "High Court of Delhi",
    "Delhi High Court": "High Court of Delhi",

    # Jammu & Kashmir High Court variations
    "HIGH COURT OF JAMMU & KASHMIR AND LADAKH AT JAMMU": "High Court of Jammu & Kashmir and Ladakh",
    "HIGH COURT OF JAMMU AND KASHMIR AND LADAKH AT JAMMU": "High Court of Jammu & Kashmir and Ladakh",
    "HIGH COURT OF JAMMU AND KASHMIR AND LADAKH": "High Court of Jammu & Kashmir and Ladakh",
    "HIGH COURT OF JAMMU & KASHMIR AND LADAKH": "High Court of Jammu & Kashmir and Ladakh",
    "HIGH COURT OF JAMMU AND KASHMIR & LADAKH AT JAMMU": "High Court of Jammu & Kashmir and Ladakh",
    "J&K High Court": "High Court of Jammu & Kashmir and Ladakh",

    # Andhra Pradesh High Court variations
    "HIGH COURT OF ANDHRA PRADESH": "High Court of Andhra Pradesh",
    "HIGH COURT OF ANDHRA PRADESH AT AMARAVATI": "High Court of Andhra Pradesh",
    "High Court of Andhra Pradesh at Amaravati": "High Court of Andhra Pradesh",
    "High Court of Andhra Pradesh at Amarava": "High Court of Andhra Pradesh",
    "High Court of Andhra Pradesh, Amaravati": "High Court of Andhra Pradesh",
    "High Court of Andhra Pradesh Amaravati": "High Court of Andhra Pradesh",
    "HIGH COURT OF ANDHRA PRADESH, AMARAVATI": "High Court of Andhra Pradesh",
    "HIGH COURT OF ANDHRA PRADESH AT AMARAV": "High Court of Andhra Pradesh",
    "HIGH COURT OF ANDHRA PRADESH AT AMARAVATU": "High Court of Andhra Pradesh",
    "HIGH COURT OF ANDHRA PRADESH AT AMARAVATHI": "High Court of Andhra Pradesh",
    "HIGH COURT OF ANDHRA PRADESH AT AMARAVATJ": "High Court of Andhra Pradesh",
    "HIGH COURT OF ANDHRA PRADESH: AMARAVATI": "High Court of Andhra Pradesh",
    "HIGH COURT OF ANDHRA PRADESH:: AMARAVATI": "High Court of Andhra Pradesh",
    "HIGH COURT OF ANDHRA PRADESH::AMARAVATI": "High Court of Andhra Pradesh",
    "High Court of Andhra Pradesh": "High Court of Andhra Pradesh",
    "Andhra Pradesh High Court": "High Court of Andhra Pradesh",
}

def analyze_current_court_names() -> list:
    """Show all unique court names and their counts"""
    db = DatabaseLoader()
    session = db.SessionLocal()

    try:
        # Query unique court names with counts
        court_counts = (
            session.query(Case.court, func.count(Case.id))
            .group_by(Case.court)
            .order_by(func.count(Case.id).desc())
            .all()
        )

        logger.info(f"\n{'='*60}")
        logger.info("CURRENT COURT NAME DISTRIBUTION")
        logger.info(f"{'='*60}")

        for court, count in court_counts:
            court_name = court if court else "NULL/Unknown"
            logger.info(f"{court_name:<50} {count:>5} cases")

        logger.info(f"{'='*60}")
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
        logger.info("Starting court name standardization...")

        for old_name, new_name in COURT_STANDARDIZATION.items():
            # Count how many cases will be updated
            count = session.query(Case).filter(Case.court == old_name).count()

            if count > 0:
                # Update cases
                session.query(Case).filter(Case.court == old_name).update(
                    {Case.court: new_name},
                    synchronize_session=False
                )

                logger.info(f"✓ Updated {count} cases: '{old_name}' → '{new_name}'")
                total_updated += count

        session.commit()
        logger.success(f"\nTotal cases updated: {total_updated}")

        # Show new distribution
        logger.info("\nNEW COURT DISTRIBUTION:")
        analyze_current_court_names()

    except Exception as e:
        session.rollback()
        logger.error(f"Error during standardization: {e}")
        raise
    finally:
        session.close()

def main():
    logger.info("="*60)
    logger.info("COURT NAME STANDARDIZATION")
    logger.info("="*60)

    # Step 1: Show current state
    logger.info("\nStep 1: Analyzing current court names...")
    analyze_current_court_names()

    # Step 2: Confirm before proceeding
    logger.info(f"\nAbout to standardize {len(COURT_STANDARDIZATION)} court name variations")
    response = input("Proceed? (yes/no): ")

    if response.lower() != 'yes':
        logger.warning("Standardization cancelled by user")
        return

    # Step 3: Standardize
    standardize_court_names()

    logger.success("✅ Court name standardization complete!")

if __name__ == "__main__":
    main()
