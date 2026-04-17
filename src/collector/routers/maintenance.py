from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from src.collector.database import get_db, LogEntry, Snapshot
from src.collector.settings import load_config
from src.collector.ai_processor.noc_engine import run_noc_analysis
from src.collector.ai_processor.siem_engine import run_siem_analysis
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/purge")
async def purge_old_data(db: Session = Depends(get_db)):
    config = load_config()
    retention_days = config.get("maintenance", {}).get("retention_days", 7)
    
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    
    try:
        # Purge logs
        deleted_logs = db.query(LogEntry).filter(LogEntry.timestamp < cutoff_date).delete()
        
        # Purge snapshots
        deleted_snapshots = db.query(Snapshot).filter(Snapshot.timestamp < cutoff_date).delete()
        
        db.commit()
        return {
            "status": "success", 
            "message": f"Purged data older than {retention_days} days",
            "deleted_logs": deleted_logs,
            "deleted_snapshots": deleted_snapshots
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Purge failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ai-process/noc")
async def trigger_noc_ai():
    try:
        analysis = run_noc_analysis()
        return {"status": "success", "analysis": analysis}
    except Exception as e:
        logger.error(f"Manual NOC analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ai-process/siem")
async def trigger_siem_ai():
    try:
        analysis = run_siem_analysis()
        return {"status": "success", "analysis": analysis}
    except Exception as e:
        logger.error(f"Manual SIEM analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
