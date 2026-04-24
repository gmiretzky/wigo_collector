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

# Centralized C2 Audit Log (for human-readable trails)
AUDIT_FILE = "logs/c2_audit.log"
audit_logger = logging.getLogger("wigo_audit")
audit_logger.setLevel(logging.INFO)
audit_handler = logging.FileHandler(AUDIT_FILE)
audit_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
audit_logger.addHandler(audit_handler)

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

def log_audit(user_text, reasoning, agent_name, command):
    """
    Log AI-generated commands with context.
    """
    msg = f"User: {user_text} | Reasoning: {reasoning} | Agent: {agent_name} | Action: {command}"
    audit_logger.info(msg)
