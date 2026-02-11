"""
High Court Judgment Downloader from AWS S3.
Downloads PDFs and metadata JSON from the public S3 bucket.
"""
import json
import tarfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import boto3
from botocore import UNSIGNED
from botocore.config import Config
from tqdm import tqdm
from loguru import logger

from src.config.settings import settings
from src.database.schemas import DownloadManifest


class HighCourtDownloader:
    """
    Downloads High Court judgments from AWS S3 public bucket.
    No AWS credentials needed - uses anonymous access.
    """

    def __init__(self, output_dir: str = "data/raw/high_courts"):
        """
        Initialize the downloader.

        Args:
            output_dir: Directory to save downloaded files
        """
        self.bucket_name = settings.s3_bucket_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize S3 client with unsigned requests (no credentials needed)
        self.s3_client = boto3.client(
            's3',
            region_name=settings.s3_region,
            config=Config(signature_version=UNSIGNED)
        )

        logger.info(f"High Court downloader initialized", bucket=self.bucket_name, output_dir=str(self.output_dir))

    def list_available_courts(self) -> List[str]:
        """
        List all available court codes in the S3 bucket.

        Returns:
            List of court codes (e.g., ['DL_HC', 'BH_HC', ...])
        """
        logger.info("Listing available courts from S3")

        try:
            # List objects with prefix 'data/tar/'
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix='data/tar/', Delimiter='/')

            courts = set()
            for page in pages:
                # Extract court codes from CommonPrefixes
                if 'CommonPrefixes' in page:
                    for prefix in page['CommonPrefixes']:
                        # Format: data/tar/year=YYYY/court=XX_XX/
                        parts = prefix['Prefix'].split('/')
                        for part in parts:
                            if part.startswith('court='):
                                court_code = part.split('=')[1]
                                courts.add(court_code)

            court_list = sorted(list(courts))
            logger.info(f"Found {len(court_list)} courts", courts=court_list)
            return court_list

        except Exception as e:
            logger.error(f"Failed to list courts", error=str(e))
            raise

    def list_available_years(self, court_code: str) -> List[int]:
        """
        List available years for a specific court.

        Args:
            court_code: Court code (e.g., 'DL_HC')

        Returns:
            List of years
        """
        logger.info(f"Listing available years for court", court=court_code)

        try:
            prefix = f'data/tar/'
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix, Delimiter='/')

            years = set()
            for page in pages:
                if 'CommonPrefixes' in page:
                    for prefix_obj in page['CommonPrefixes']:
                        # Format: data/tar/year=YYYY/
                        parts = prefix_obj['Prefix'].split('/')
                        for part in parts:
                            if part.startswith('year='):
                                year = int(part.split('=')[1])
                                years.add(year)

            year_list = sorted(list(years), reverse=True)
            logger.info(f"Found {len(year_list)} years for {court_code}", years=year_list)
            return year_list

        except Exception as e:
            logger.error(f"Failed to list years", court=court_code, error=str(e))
            raise

    def download_court_data(
        self,
        court_code: str,
        year: int,
        max_cases: Optional[int] = None
    ) -> DownloadManifest:
        """
        Download judgment data for a specific court and year.

        Args:
            court_code: Court code (e.g., 'DL_HC')
            year: Year to download
            max_cases: Maximum number of cases to download (None for all)

        Returns:
            DownloadManifest with download statistics
        """
        logger.info(f"Starting download", court=court_code, year=year, max_cases=max_cases)

        manifest = DownloadManifest(
            court_code=court_code,
            year=year
        )

        # Create output directory for this court/year
        court_dir = self.output_dir / court_code / str(year)
        court_dir.mkdir(parents=True, exist_ok=True)

        try:
            # List all objects for this court/year
            prefix = f'data/tar/year={year}/court={court_code}/'
            logger.debug(f"Searching S3 with prefix: {prefix}")

            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            if 'Contents' not in response:
                logger.warning(f"No data found for {court_code} in {year}")
                return manifest

            objects = response['Contents']
            logger.info(f"Found {len(objects)} objects in S3")

            # Filter for tar files and JSON metadata
            tar_files = [obj for obj in objects if obj['Key'].endswith('.tar')]
            json_files = [obj for obj in objects if obj['Key'].endswith('.json')]

            logger.info(f"Found {len(tar_files)} tar files and {len(json_files)} JSON files")

            # Download PDFs from tar files
            cases_downloaded = 0
            for tar_obj in tqdm(tar_files, desc=f"Downloading {court_code} {year}"):
                if max_cases and cases_downloaded >= max_cases:
                    break

                try:
                    tar_key = tar_obj['Key']
                    tar_filename = Path(tar_key).name
                    local_tar_path = court_dir / tar_filename

                    # Download tar file
                    self.s3_client.download_file(
                        self.bucket_name,
                        tar_key,
                        str(local_tar_path)
                    )

                    # Extract tar file
                    with tarfile.open(local_tar_path, 'r') as tar:
                        tar.extractall(path=court_dir)

                    # Remove tar file after extraction
                    local_tar_path.unlink()

                    manifest.successful_downloads += 1
                    cases_downloaded += 1

                except Exception as e:
                    logger.error(f"Failed to download/extract tar file", tar_key=tar_key, error=str(e))
                    manifest.failed_downloads += 1
                    manifest.cases.append({
                        "file": tar_key,
                        "status": "failed",
                        "error": str(e)
                    })

            # Download metadata JSON files
            for json_obj in tqdm(json_files[:max_cases] if max_cases else json_files, desc="Downloading metadata"):
                try:
                    json_key = json_obj['Key']
                    json_filename = Path(json_key).name
                    local_json_path = court_dir / json_filename

                    # Download JSON
                    self.s3_client.download_file(
                        self.bucket_name,
                        json_key,
                        str(local_json_path)
                    )

                    manifest.cases.append({
                        "file": json_key,
                        "status": "success",
                        "local_path": str(local_json_path)
                    })

                except Exception as e:
                    logger.error(f"Failed to download JSON", json_key=json_key, error=str(e))
                    manifest.cases.append({
                        "file": json_key,
                        "status": "failed",
                        "error": str(e)
                    })

            manifest.total_cases = cases_downloaded
            logger.info(
                f"Download complete",
                court=court_code,
                year=year,
                successful=manifest.successful_downloads,
                failed=manifest.failed_downloads
            )

            # Save manifest
            manifest_path = court_dir / "download_manifest.json"
            with open(manifest_path, 'w') as f:
                json.dump(manifest.model_dump(), f, indent=2, default=str)

            return manifest

        except Exception as e:
            logger.error(f"Download failed", court=court_code, year=year, error=str(e))
            raise

    def download_sample(
        self,
        n_cases: int = 100,
        courts: Optional[List[str]] = None,
        years: Optional[List[int]] = None
    ) -> List[DownloadManifest]:
        """
        Download a diverse sample of cases across multiple courts and years.

        Args:
            n_cases: Total number of cases to download
            courts: List of court codes (uses settings default if None)
            years: List of years (uses settings default if None)

        Returns:
            List of DownloadManifest objects
        """
        courts = courts or settings.target_courts
        years = years or settings.target_years

        logger.info(f"Downloading sample", n_cases=n_cases, courts=courts, years=years)

        # Distribute cases across courts and years
        cases_per_combo = n_cases // (len(courts) * len(years))
        remainder = n_cases % (len(courts) * len(years))

        manifests = []
        for court in courts:
            for year in years:
                max_cases = cases_per_combo + (1 if remainder > 0 else 0)
                remainder -= 1

                try:
                    manifest = self.download_court_data(court, year, max_cases=max_cases)
                    manifests.append(manifest)
                except Exception as e:
                    logger.error(f"Failed to download sample", court=court, year=year, error=str(e))

        total_downloaded = sum(m.successful_downloads for m in manifests)
        total_failed = sum(m.failed_downloads for m in manifests)

        logger.info(
            f"Sample download complete",
            total_successful=total_downloaded,
            total_failed=total_failed
        )

        return manifests

    def get_downloaded_pdfs(self, court_code: Optional[str] = None, year: Optional[int] = None) -> List[Path]:
        """
        Get list of all downloaded PDF files.

        Args:
            court_code: Filter by court code (optional)
            year: Filter by year (optional)

        Returns:
            List of PDF file paths
        """
        if court_code and year:
            search_dir = self.output_dir / court_code / str(year)
        elif court_code:
            search_dir = self.output_dir / court_code
        else:
            search_dir = self.output_dir

        if not search_dir.exists():
            return []

        pdf_files = list(search_dir.rglob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files", directory=str(search_dir))
        return pdf_files
