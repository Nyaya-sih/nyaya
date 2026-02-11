#!/usr/bin/env python3
"""
Script to download a sample of High Court judgments from S3.
Downloads 100 cases by default across specified courts and years.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_logging
from src.data_pipeline.downloaders.hc_downloader import HighCourtDownloader
from src.config.settings import settings
from loguru import logger


def main():
    """Download sample cases."""
    # Setup logging
    setup_logging()

    logger.info("=" * 80)
    logger.info("HIGH COURT JUDGMENT DOWNLOADER")
    logger.info("=" * 80)

    # Initialize downloader
    downloader = HighCourtDownloader()

    # Print configuration
    logger.info(f"Configuration:")
    logger.info(f"  Target courts: {settings.target_courts}")
    logger.info(f"  Target years: {settings.target_years}")
    logger.info(f"  Max cases to download: {settings.download_max_cases}")
    logger.info("")

    # List available courts (optional - for informational purposes)
    try:
        logger.info("Listing available courts from S3...")
        available_courts = downloader.list_available_courts()
        logger.info(f"Available courts: {', '.join(available_courts[:10])}...")
    except Exception as e:
        logger.warning(f"Could not list available courts: {e}")

    # Download sample
    logger.info("")
    logger.info("Starting download...")
    logger.info(f"This will download approximately {settings.download_max_cases} cases")
    logger.info("")

    try:
        manifests = downloader.download_sample(
            n_cases=settings.download_max_cases,
            courts=settings.target_courts,
            years=settings.target_years
        )

        # Print summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("DOWNLOAD SUMMARY")
        logger.info("=" * 80)

        total_successful = 0
        total_failed = 0

        for manifest in manifests:
            logger.info(f"Court: {manifest.court_code}, Year: {manifest.year}")
            logger.info(f"  Successful: {manifest.successful_downloads}")
            logger.info(f"  Failed: {manifest.failed_downloads}")
            logger.info(f"  Total: {manifest.total_cases}")
            logger.info("")

            total_successful += manifest.successful_downloads
            total_failed += manifest.failed_downloads

        logger.info(f"Overall:")
        logger.info(f"  Total successful downloads: {total_successful}")
        logger.info(f"  Total failed downloads: {total_failed}")
        logger.info(f"  Success rate: {total_successful / (total_successful + total_failed) * 100:.1f}%")

        # List downloaded PDFs
        logger.info("")
        logger.info("Verifying downloaded files...")
        pdf_files = downloader.get_downloaded_pdfs()
        logger.info(f"Total PDF files on disk: {len(pdf_files)}")

        if pdf_files:
            logger.info(f"Sample files:")
            for pdf in pdf_files[:5]:
                logger.info(f"  {pdf}")

        logger.info("")
        logger.info("✅ Download complete!")
        logger.info(f"Files saved to: {downloader.output_dir}")

    except Exception as e:
        logger.error(f"Download failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
