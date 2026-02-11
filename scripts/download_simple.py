#!/usr/bin/env python3
"""
Simple script to download sample PDFs from the actual S3 structure.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from tqdm import tqdm

# Create S3 client
s3 = boto3.client('s3', region_name='ap-south-1', config=Config(signature_version=UNSIGNED))
bucket = 'indian-high-court-judgments'

# Create output directory
output_dir = Path('data/raw/sample_pdfs')
output_dir.mkdir(parents=True, exist_ok=True)

print("Downloading sample PDFs from Indian High Court S3 bucket...")
print(f"Saving to: {output_dir}")
print()

# Download PDFs from recent years
downloaded = 0
skipped = 0
target = 1000

# Expand year range for more diversity
for year in [2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015]:
    if downloaded >= target:
        break

    print(f"\n📅 Checking year {year}...")
    prefix = f'data/pdf/year={year}/'

    # Use pagination to get more results
    paginator = s3.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(
        Bucket=bucket,
        Prefix=prefix,
        PaginationConfig={'MaxItems': 2000}  # Get up to 2000 items per year
    )

    year_downloaded = 0
    for page in page_iterator:
        if downloaded >= target:
            break

        if 'Contents' not in page:
            continue

        for obj in page['Contents']:
            if downloaded >= target:
                break

            key = obj['Key']
            if not key.endswith('.pdf'):
                continue

            # Extract filename
            filename = Path(key).name
            local_path = output_dir / filename

            # Skip if already exists
            if local_path.exists():
                skipped += 1
                continue

            try:
                print(f"Downloading: {filename}...")
                s3.download_file(bucket, key, str(local_path))
                downloaded += 1
                year_downloaded += 1
                print(f"  ✓ Downloaded ({obj['Size']} bytes)")
            except Exception as e:
                print(f"  ✗ Failed: {e}")

    print(f"  Year {year}: {year_downloaded} new files")

print()
print(f"✅ Downloaded {downloaded} NEW PDFs to {output_dir}")
print(f"⏭️  Skipped {skipped} existing files")
print(f"📊 Total files in directory: {len(list(output_dir.glob('*.pdf')))}")
print()
print("Next step: Run 'python scripts/run_extraction_simple.py' to extract metadata")
