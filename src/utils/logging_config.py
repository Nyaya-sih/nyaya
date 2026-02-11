"""
Structured logging configuration using loguru.
"""
import sys
from pathlib import Path
from loguru import logger
from src.config.settings import settings


def setup_logging() -> None:
    """
    Configure structured logging with loguru.

    Sets up console and file logging with appropriate formats and levels.
    """
    # Remove default handler
    logger.remove()

    # Console handler with colored output
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )

    # Ensure log directory exists
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # File handler with JSON format for structured logging
    logger.add(
        settings.log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.log_level,
        rotation="100 MB",  # Rotate when file reaches 100MB
        retention="30 days",  # Keep logs for 30 days
        compression="zip",  # Compress rotated logs
        serialize=False,  # JSON serialization (set to True if you want JSON logs)
    )

    logger.info("Logging initialized", log_level=settings.log_level, log_file=settings.log_file)


def get_logger(name: str):
    """
    Get a logger instance for a specific module.

    Args:
        name: Name of the module (typically __name__)

    Returns:
        Logger instance
    """
    return logger.bind(module=name)
