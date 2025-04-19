from loguru import logger
import sys

# Configure logger with detailed formatting for debugging
logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} - {message}",
    level="DEBUG"
)

# Create a custom logger instance for the application
app_logger = logger

# Enhanced logging functions for critical operations
def log_customer_creation(phone_number: str, success: bool, message: str = ""):
    """Log customer creation or update operation with status and optional message."""
    status = "SUCCESS" if success else "FAILURE"
    app_logger.info(f"Customer Creation | Phone: {phone_number} | Status: {status} | {message}")

def log_customer_retrieval(phone_number: str, found: bool):
    """Log customer retrieval operation with status."""
    status = "FOUND" if found else "NOT FOUND"
    app_logger.info(f"Customer Retrieval | Phone: {phone_number} | Status: {status}")

def log_history_storage(phone_number: str, success: bool, message: str = ""):
    """Log conversation history storage operation with status and optional message."""
    status = "SUCCESS" if success else "FAILURE"
    app_logger.info(f"History Storage | Phone: {phone_number} | Status: {status} | {message}")

def log_history_retrieval(phone_number: str, count: int):
    """Log conversation history retrieval operation with the number of entries retrieved."""
    app_logger.info(f"History Retrieval | Phone: {phone_number} | Entries Retrieved: {count}")

def log_message_processing(phone_number: str, status: str, message: str = ""):
    """Log message processing operation with status and optional message."""
    app_logger.info(f"Message Processing | Phone: {phone_number} | Status: {status} | {message}")
