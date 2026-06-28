
"""Logger configuration module

Use Loguru to configure application logs
"""

import sys
from loguru import logger
from app.config import config


def setup_logger():
    """Configure logging system

    Configure the global logger following Loguru best practices:
    1. Remove default handler
    2. Add colored console output
    3. Add file output with daily rotation, compression, and async writes
    """
    # Remove default handler
    logger.remove()

    # Add colored console output format
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{module}</cyan>.<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
        level="DEBUG" if config.debug else "INFO",
        colorize=True,
        backtrace=True,  # Show full exception stack traces
        diagnose=config.debug,  # Show variable values in debug mode
    )

    # Add file output with daily rotation and automatic compression
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # Rotate log file daily at midnight
        retention="7 days",  # Keep only the last 7 days of logs
        compression="zip",  # Compress expired logs as zip
        encoding="utf-8",  # Avoid encoding issues
        enqueue=True,  # Async write for better performance and less IO blocking
        backtrace=True,  # Show full exception stack traces
        diagnose=True,  # Show variable values for debugging
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {module}.{function}:{line} | {message}",
    )

setup_logger()
