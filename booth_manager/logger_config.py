import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import functools
from PySide6.QtWidgets import QMessageBox

# Configure rotating file and console logging
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, 'booth_manager.log')
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
    ]
)
logger = logging.getLogger(__name__)

# Decorator to catch and log exceptions in UI methods
def handle_exceptions(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Unhandled exception in {func.__name__}")
            QMessageBox.critical(None, "오류", f"예기치 못한 오류가 발생했습니다:\n{e}")
    return wrapper 