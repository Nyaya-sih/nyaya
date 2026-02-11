#!/usr/bin/env python3
"""
Download cases from multiple High Courts to create a balanced dataset.

Strategy: Target court codes we don't have many cases from yet.

Current distribution:
- Patna HC (19_16): 5,901 cases (85%)
- Sikkim HC: 714 cases (10%)
- Manipur HC: 304 cases (4%)
- Others: <1%

Target: Download ~3,500 cases from other courts to achieve:
- Patna: ~55% (current 5,901)
- Others: ~45% (add 3,500 new)
- Total: ~10,500 cases

This will take 2-3 hours for download + 2-3 hours for extraction.
"""

import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from loguru import logger
from tqdm import tqdm
from collections import defaultdict

# Priority courts to download from (excluding 19_16 Patna which we have plenty of)
# These are the major court codes from S3 bucket
DOWNLOAD_CONFIG = [
    {'code': '27_1', 'target': 800, 'name': 'Court 27_1'},  # Likely Delhi HC
    {'code': '18_6', 'target': 700, 'name': 'Court 18_6'},  # Likely Bombay HC
    {'code': '10_8', 'target': 600, 'name': 'Court 10_8'},  # Major court
    {'code': '28_2', 'target': 500, 'name': 'Court 28_2'},  # Likely Karnataka HC
    {'code': '29_3', 'target': 400, 'name': 'Court 29_3'},  # Likely Madras HC
    {'code': '7_26', 'target': 300, 'name': 'Court 7_26'},  # Likely Calcutta HC
    {'code': '1_12', 'target': 200, 'name': 'Court 1_12'},  # Likely Allahabad HC
]

def download_from_court(s3_client, bucket, court_config, years, output_base_dir):
    """Download cases from a specific court"""

    court_code = court_config['code']
    target_cases = court_config['target']
    court_name = court_config['name']

    logger.info(f"\n{'='*60}")
    logger.info(f"DOWNLOADING FROM {court_name} (code: {court_code})")
    logger.info(f"{'='*60}")
    logger.info(f"Target: {target_cases} cases")
    logger.info(f"Years: {years}")

    downloaded_count = 0
    skipped_count = 0
    failed_count = 0

    output_dir = output_base_dir / f"court_{court_code}"
    output_dir.mkdir(parents=True, exist_ok=True)

    for year in years:
        if downloaded_count >= target_cases:
            break

        remaining = target_cases - downloaded_count

        logger.info(f"\n📅 Year {year} (need {remaining} more cases)")

        try:
            prefix = f'data/pdf/year={year}/court={court_code}/'

            # Use paginator to get all files
            paginator = s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=bucket,
                Prefix=prefix,
                PaginationConfig={'MaxItems': remaining + 100}
            )

            year_downloaded = 0

            for page in page_iterator:
                if downloaded_count >= target_cases:
                    break

                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    if downloaded_count >= target_cases:
                        break

                    key = obj['Key']
                    if not key.endswith('.pdf'):
                        continue

                    filename = Path(key).name
                    local_path = output_dir / filename

                    # Skip if already exists
                    if local_path.exists():
                        skipped_count += 1
                        continue

                    try:
                        s3_client.download_file(bucket, key, str(local_path))
                        downloaded_count += 1
                        year_downloaded += 1

                        if downloaded_count % 50 == 0:
                            logger.info(f"  ✓ {downloaded_count}/{target_cases} downloaded")

                    except Exception as e:
                        failed_count += 1
                        if failed_count <= 3:
                            logger.warning(f"  ✗ Failed: {filename}: {e}")

            if year_downloaded > 0:
                logger.success(f"  ✓ Downloaded {year_downloaded} cases from {year}")

        except Exception as e:
            logger.error(f"Error downloading from {court_name} {year}: {e}")
            continue

    logger.success(f"\n✓ Total from {court_name}: {downloaded_count} cases downloaded")

    return {
        'court_code': court_code,
        'court_name': court_name,
        'downloaded': downloaded_count,
        'skipped': skipped_count,
        'failed': failed_count,
    }

def main():
    parser = argparse.ArgumentParser(description='Download diverse High Court cases')
    parser.add_argument(
        '--total',
        type=int,
        default=3500,
        help='Total number of cases to download'
    )
    parser.add_argument(
        '--years',
        nargs='+',
        default=['2023', '2022', '2021', '2020', '2019'],
        help='Years to download from'
    )

    args = parser.parse_args()

    logger.info("="*60)
    logger.info("DIVERSE COURT CASE DOWNLOAD")
    logger.info("="*60)
    logger.info(f"Target total: {args.total} cases")
    logger.info(f"Years: {', '.join(args.years)}")

    # Initialize S3 client
    s3 = boto3.client('s3', region_name='ap-south-1', config=Config(signature_version=UNSIGNED))
    bucket = 'indian-high-court-judgments'

    output_base_dir = Path('data/raw/diverse_courts')
    output_base_dir.mkdir(parents=True, exist_ok=True)

    # Download from each court
    all_results = []
    total_downloaded = 0

    for court_config in DOWNLOAD_CONFIG:
        if total_downloaded >= args.total:
            logger.info(f"\n✓ Reached target of {args.total} cases")
            break

        result = download_from_court(
            s3,
            bucket,
            court_config,
            args.years,
            output_base_dir
        )

        all_results.append(result)
        total_downloaded += result['downloaded']

    # Print summary
    logger.success(f"\n{'='*60}")
    logger.success(f"DOWNLOAD COMPLETE")
    logger.success(f"{'='*60}")

    logger.info("\nDownload Summary:")
    for result in all_results:
        logger.info(f"  {result['court_name']:20s} {result['downloaded']:>5} cases")

    logger.success(f"\nTotal downloaded: {total_downloaded} cases")
    logger.success(f"Estimated extraction cost: ${total_downloaded * 0.00035:.2f}")
    logger.success(f"Estimated extraction time: ~{total_downloaded * 2.5 / 60:.0f} minutes")

    logger.info("\nNext steps:")
    logger.info("  1. Run: python scripts/09_extract_diverse.py")
    logger.info("  2. Wait for extraction to complete")
    logger.info("  3. Run: python scripts/10_final_validation.py")

if __name__ == "__main__":
    main()
