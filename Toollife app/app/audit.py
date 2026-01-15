import os
import logging
from .config import AUDIT_LOG_FILE, LOGS_DIR

# Ensure logs directory exists BEFORE configuring logging
os.makedirs(LOGS_DIR, exist_ok=True)

logging.basicConfig(
    filename=AUDIT_LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

def log_audit(user: str, action: str):
    logging.info(f"User: {user} | Action: {action}")
