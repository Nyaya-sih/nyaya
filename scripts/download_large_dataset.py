#!/usr/bin/env python3
"""
Download large diverse dataset from Indian High Court S3 bucket.
Targets multiple courts and years for maximum diversity.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from tqdm import tqdm
from collections import defaultdict

# Create S3 client
s3 = boto3.client('s3', region_name='ap-south-1', config=Config(signature_version=UNSIGNED))
bucket = 'indian-high-court-judgments'

# Create output directory
output_dir = Path('data/raw/sample_pdfs')
output_dir.mkdir(parents=True, exist_ok=True)

print("🏛️  Downloading diverse dataset from Indian High Court S3 bucket...")
print(f"📁 Saving to: {output_dir}")
print()

# Configuration
target = 6500
years = [2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015, 2014, 2013]
downloaded = 0
skipped = 0
failed = 0
court_stats = defaultdict(int)

# Strategy: Distribute downloads across courts and years for diversity
# Get ~250 cases per year from different courts

for year in years:
    if downloaded >= target:
        break

    print(f"\n📅 Year {year}")
    print("=" * 60)

    year_target = min(600, target - downloaded)  # Up to 600 per year
    year_downloaded = 0

    # Get list of courts for this year
    prefix = f'data/pdf/year={year}/'
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=10, Delimiter='/')

    if 'CommonPrefixes' not in response:
        print(f"  ⚠️  No courts found for {year}")
        continue

    courts = [cp['Prefix'] for cp in response['CommonPrefixes']]
    print(f"  📊 Found {len(courts)} courts")

    # Download from each court
    for court_prefix in courts:
        if year_downloaded >= year_target or downloaded >= target:
            break

        court_code = court_prefix.split('/')[-2]

        # Use pagination to get files
        paginator = s3.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(
            Bucket=bucket,
            Prefix=court_prefix,
            PaginationConfig={'MaxItems': 500}  # Limit per court
        )

        court_downloaded = 0

        for page in page_iterator:
            if year_downloaded >= year_target or downloaded >= target:
                break

            if 'Contents' not in page:
                continue

            for obj in page['Contents']:
                if year_downloaded >= year_target or downloaded >= target:
                    break

                key = obj['Key']
                if not key.endswith('.pdf'):
                    continue

                filename = Path(key).name
                local_path = output_dir / filename

                # Skip if already exists
                if local_path.exists():
                    skipped += 1
                    continue

                try:
                    s3.download_file(bucket, key, str(local_path))
                    downloaded += 1
                    year_downloaded += 1
                    court_downloaded += 1
                    court_stats[court_code] += 1

                    # Print progress every 50 files
                    if downloaded % 50 == 0:
                        print(f"    ✓ {downloaded}/{target} downloaded (Year {year}, {court_code})")

                except Exception as e:
                    failed += 1
                    if failed <= 5:  # Only print first few errors
                        print(f"    ✗ Failed: {filename}: {e}")

        if court_downloaded > 0:
            print(f"    {court_code}: {court_downloaded} cases")

    print(f"  ✅ Year {year}: {year_downloaded} cases downloaded")

print("\n" + "=" * 60)
print("📊 DOWNLOAD SUMMARY")
print("=" * 60)
print(f"✅ Downloaded: {downloaded} NEW PDFs")
print(f"⏭️  Skipped: {skipped} existing files")
print(f"❌ Failed: {failed} files")
print(f"📁 Total in directory: {len(list(output_dir.glob('*.pdf')))}")
print()
print(f"📈 Court Distribution (top 10):")
sorted_courts = sorted(court_stats.items(), key=lambda x: x[1], reverse=True)
for court, count in sorted_courts[:10]:
    print(f"  {court}: {count} cases")

print("\n" + "=" * 60)
print("✅ DOWNLOAD COMPLETE!")
print("=" * 60)
print("\nNext step: Run extraction pipeline")
print("  python scripts/run_extraction_simple.py")
