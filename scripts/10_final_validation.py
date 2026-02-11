#!/usr/bin/env python3
"""
Comprehensive validation report for production readiness.

Checks:
1. Court distribution (no court >30%)
2. Confidence distribution (>70% cases with confidence >70%)
3. Field completeness (>90% have critical fields)
4. Temporal distribution (spread across years)
5. Case type diversity
6. Validation status (<5% invalid)

Outputs: PRODUCTION READY: YES/NO
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.models import Case
from src.data_pipeline.loaders.db_loader import DatabaseLoader
from loguru import logger
from sqlalchemy import func
from datetime import datetime
from collections import Counter
import json

def generate_comprehensive_report():
    """Generate full validation report"""

    db = DatabaseLoader()
    session = db.SessionLocal()

    try:
        all_cases = session.query(Case).all()
        total_cases = len(all_cases)

        report = {
            'total_cases': total_cases,
            'timestamp': datetime.now().isoformat(),
        }

        # 1. Court Distribution
        logger.info("\n" + "="*60)
        logger.info("1. COURT DISTRIBUTION")
        logger.info("="*60)

        court_counts = Counter([c.court for c in all_cases if c.court])
        total_with_court = sum(court_counts.values())

        for court, count in court_counts.most_common(15):
            percentage = count / total_with_court * 100
            logger.info(f"{court:<50} {count:>5} ({percentage:>5.1f}%)")

        max_court_pct = max(court_counts.values()) / total_with_court * 100 if court_counts else 0
        court_balance_ok = max_court_pct < 30

        logger.info(f"\nMax court percentage: {max_court_pct:.1f}%")
        status = '✓ PASS' if court_balance_ok else '✗ FAIL (>30%)'
        logger.info(f"Court balance: {status}")

        report['court_distribution'] = dict(court_counts.most_common(15))
        report['max_court_percentage'] = max_court_pct
        report['court_balance_ok'] = court_balance_ok

        # 2. Confidence Distribution
        logger.info("\n" + "="*60)
        logger.info("2. CONFIDENCE DISTRIBUTION")
        logger.info("="*60)

        confidence_scores = [c.average_confidence for c in all_cases if c.average_confidence]
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0

        confidence_buckets = {
            '90-100%': sum(1 for c in confidence_scores if c >= 0.9),
            '80-90%': sum(1 for c in confidence_scores if 0.8 <= c < 0.9),
            '70-80%': sum(1 for c in confidence_scores if 0.7 <= c < 0.8),
            '60-70%': sum(1 for c in confidence_scores if 0.6 <= c < 0.7),
            '<60%': sum(1 for c in confidence_scores if c < 0.6),
        }

        for bucket, count in confidence_buckets.items():
            pct = count / len(confidence_scores) * 100 if confidence_scores else 0
            logger.info(f"{bucket:<15} {count:>5} cases ({pct:>5.1f}%)")

        high_confidence_pct = (confidence_buckets['90-100%'] + confidence_buckets['80-90%']) / len(confidence_scores) * 100 if confidence_scores else 0
        confidence_ok = high_confidence_pct > 50 and avg_confidence > 0.75

        logger.info(f"\nAverage confidence: {avg_confidence:.1%}")
        logger.info(f"High confidence (>80%): {high_confidence_pct:.1f}%")
        status = '✓ PASS' if confidence_ok else '✗ FAIL'
        logger.info(f"Confidence quality: {status}")

        report['average_confidence'] = avg_confidence
        report['high_confidence_percentage'] = high_confidence_pct
        report['confidence_ok'] = confidence_ok

        # 3. Field Completeness
        logger.info("\n" + "="*60)
        logger.info("3. FIELD COMPLETENESS")
        logger.info("="*60)

        critical_fields = {
            'case_title': sum(1 for c in all_cases if c.case_title),
            'court': sum(1 for c in all_cases if c.court),
            'date_of_judgment': sum(1 for c in all_cases if c.date_of_judgment),
            'verdict': sum(1 for c in all_cases if c.verdict),
            'case_type': sum(1 for c in all_cases if c.case_type),
        }

        for field, count in critical_fields.items():
            pct = count / total_cases * 100 if total_cases else 0
            status = '✓' if pct > 90 else '✗'
            logger.info(f"{status} {field:<20} {count:>5}/{total_cases} ({pct:>5.1f}%)")

        fields_ok = all(count / total_cases > 0.9 for count in critical_fields.values()) if total_cases else False
        status = '✓ PASS' if fields_ok else '✗ FAIL (<90%)'
        logger.info(f"\nField completeness: {status}")

        report['field_completeness'] = {k: v/total_cases for k, v in critical_fields.items()} if total_cases else {}
        report['fields_ok'] = fields_ok

        # 4. Temporal Distribution
        logger.info("\n" + "="*60)
        logger.info("4. TEMPORAL DISTRIBUTION")
        logger.info("="*60)

        years = [c.date_of_judgment.year for c in all_cases if c.date_of_judgment]
        year_counts = Counter(years)

        for year in sorted(year_counts.keys(), reverse=True):
            count = year_counts[year]
            pct = count / len(years) * 100 if years else 0
            logger.info(f"{year}: {count:>5} cases ({pct:>5.1f}%)")

        year_range = max(years) - min(years) if years else 0
        temporal_ok = year_range >= 5

        logger.info(f"\nYear range: {min(years) if years else 'N/A'} - {max(years) if years else 'N/A'} ({year_range} years)")
        status = '✓ PASS' if temporal_ok else '✗ FAIL (<5 years)'
        logger.info(f"Temporal diversity: {status}")

        report['year_range'] = year_range
        report['temporal_ok'] = temporal_ok

        # 5. Case Type Distribution
        logger.info("\n" + "="*60)
        logger.info("5. CASE TYPE DISTRIBUTION")
        logger.info("="*60)

        case_types = Counter([c.case_type for c in all_cases if c.case_type])

        for case_type, count in case_types.most_common(10):
            pct = count / total_cases * 100 if total_cases else 0
            logger.info(f"{case_type:<30} {count:>5} ({pct:>5.1f}%)")

        case_type_diversity = len(case_types)
        diversity_ok = case_type_diversity >= 5

        logger.info(f"\nUnique case types: {case_type_diversity}")
        status = '✓ PASS' if diversity_ok else '✗ FAIL (<5 types)'
        logger.info(f"Case type diversity: {status}")

        report['case_type_diversity'] = case_type_diversity
        report['diversity_ok'] = diversity_ok

        # 6. Validation Status
        logger.info("\n" + "="*60)
        logger.info("6. VALIDATION STATUS")
        logger.info("="*60)

        validation_counts = Counter([c.validation_status for c in all_cases])

        for status_val, count in validation_counts.items():
            pct = count / total_cases * 100 if total_cases else 0
            logger.info(f"{status_val:<20} {count:>5} ({pct:>5.1f}%)")

        invalid_pct = validation_counts.get('invalid', 0) / total_cases * 100 if total_cases else 0
        validation_ok = invalid_pct < 5

        logger.info(f"\nInvalid percentage: {invalid_pct:.1f}%")
        status = '✓ PASS' if validation_ok else '✗ FAIL (>5%)'
        logger.info(f"Validation quality: {status}")

        report['invalid_percentage'] = invalid_pct
        report['validation_ok'] = validation_ok

        # 7. Overall Production Readiness
        logger.info("\n" + "="*60)
        logger.info("PRODUCTION READINESS ASSESSMENT")
        logger.info("="*60)

        criteria = {
            'Total cases >= 10,000': total_cases >= 10000,
            'Court balance (<30% any court)': court_balance_ok,
            'Avg confidence >75%': confidence_ok,
            'Field completeness >90%': fields_ok,
            'Temporal diversity (5+ years)': temporal_ok,
            'Case type diversity (5+ types)': diversity_ok,
            'Invalid rate <5%': validation_ok,
        }

        for criterion, passed in criteria.items():
            status = '✓ PASS' if passed else '✗ FAIL'
            logger.info(f"{status} {criterion}")

        production_ready = all(criteria.values())

        logger.info("\n" + "="*60)
        if production_ready:
            logger.success("🎉 PRODUCTION READY: YES")
            logger.success("Dataset meets all quality criteria!")
        else:
            logger.warning("⚠️  PRODUCTION READY: NO")
            logger.warning("Some criteria not met. Review failures above.")
        logger.info("="*60)

        report['production_ready'] = production_ready
        report['criteria'] = criteria

        # Save report
        report_path = Path("data/processed/production_readiness_report.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"\nFull report saved to: {report_path}")

        return report

    finally:
        session.close()

def main():
    logger.info("="*60)
    logger.info("FINAL PRODUCTION READINESS VALIDATION")
    logger.info("="*60)

    report = generate_comprehensive_report()

    if report['production_ready']:
        logger.success("\n✅ Dataset is production-ready!")
        logger.success("You can now proceed to Feature 3: Similar Case Retrieval")
    else:
        logger.warning("\n⚠️ Dataset needs more work")
        logger.warning("Review the failures and address them:")

        for criterion, passed in report['criteria'].items():
            if not passed:
                logger.warning(f"  ✗ {criterion}")

if __name__ == "__main__":
    main()
