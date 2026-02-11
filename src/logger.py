import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(log_file_path):
    """
    Sets up a rotating file logger.
    Logs are written to the specified file path.
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    logger = logging.getLogger("ytrss")
    logger.setLevel(logging.DEBUG)

    # Check if handler already exists to avoid duplicate logs
    if not logger.handlers:
        # Create a file handler that rotates logs (max 2MB, keep 2 backups)
        handler = RotatingFileHandler(log_file_path, maxBytes=2*1024*1024, backupCount=2)
        
        # Create a logging format
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s - %(message)s')
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)

    return logger

def get_logger():
    """Returns the configured logger instance."""
    return logging.getLogger("ytrss")
