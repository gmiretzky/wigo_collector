from apscheduler.schedulers.background import BackgroundScheduler
from src.collector.ai_processor.noc_engine import run_noc_analysis
from src.collector.ai_processor.siem_engine import run_siem_analysis
from src.collector.settings import load_config
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

def start_scheduler():
    config = load_config()
    scheduler_config = config.get("scheduler", {})
    
    noc_interval = scheduler_config.get("noc_interval_hours", 4)
    siem_interval = scheduler_config.get("siem_interval_hours", 4)

    # Add jobs
    scheduler.add_job(run_noc_analysis, 'interval', hours=noc_interval, id='noc_job')
    scheduler.add_job(run_siem_analysis, 'interval', hours=siem_interval, id='siem_job')
    
    scheduler.start()
    logger.info(f"Scheduler started. NOC every {noc_interval}h, SIEM every {siem_interval}h.")

def stop_scheduler():
    scheduler.shutdown()
