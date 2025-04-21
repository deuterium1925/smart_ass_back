from loguru import logger
import sys

# Configure logger with detailed formatting for debugging
logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} - {message}",
    level="DEBUG"
)

# Custom logger instance for the application
app_logger = logger

# Logging utility functions for critical operations
def log_customer_creation(phone_number: str, success: bool, message: str = ""):
    """Log the status of customer creation or update operation."""
    status = "SUCCESS" if success else "FAILURE"
    app_logger.info(f"Customer Creation | Phone: {phone_number} | Status: {status} | {message}")

def log_customer_retrieval(phone_number: str, found: bool):
    """Log the status of customer retrieval operation."""
    status = "FOUND" if found else "NOT FOUND"
    app_logger.info(f"Customer Retrieval | Phone: {phone_number} | Status: {status}")

def log_history_storage(phone_number: str, success: bool, message: str = ""):
    """Log the status of conversation history storage operation."""
    status = "SUCCESS" if success else "FAILURE"
    app_logger.info(f"History Storage | Phone: {phone_number} | Status: {status} | {message}")

def log_history_retrieval(phone_number: str, count: int):
    """Log the number of conversation history entries retrieved."""
    app_logger.info(f"History Retrieval | Phone: {phone_number} | Entries Retrieved: {count}")

def log_message_processing(phone_number: str, status: str, message: str = ""):
    """Log the status of message processing operation."""
    app_logger.info(f"Message Processing | Phone: {phone_number} | Status: {status} | {message}")
