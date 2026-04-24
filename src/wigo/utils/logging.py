import logging
import os
from datetime import datetime

# Centralized C2 Audit Log
LOG_FILE = "logs/c2_comms.log"
os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("wigo_c2")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] [%(trace_id)s] %(message)s'))
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(stream_handler)

def log_c2(level, trace_id, message):
    extra = {'trace_id': trace_id or 'SYSTEM'}
    if level == "INFO":
        logger.info(message, extra=extra)
    elif level == "DEBUG":
        logger.debug(message, extra=extra)
    elif level == "ERROR":
        logger.error(message, extra=extra)
    elif level == "WARNING":
        logger.warning(message, extra=extra)
