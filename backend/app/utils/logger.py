import os
from loguru import logger
from app.core.config import get_settings

def setup_logger():
    settings = get_settings()
    os.makedirs("logs", exist_ok=True)
    logger.remove()  # Remove default handler
    logger.add(
        sink="logs/app.log",
        level=settings.LOG_LEVEL,
        rotation="1 MB",
        retention="7 days",
        compression="zip",
    )
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level=settings.LOG_LEVEL,
    )
    return logger

app_logger = setup_logger()