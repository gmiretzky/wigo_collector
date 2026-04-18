from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from src.collector.database import get_db, LogEntry, Snapshot, Machine
from src.collector.settings import load_config
from src.collector.ai_processor.noc_engine import run_noc_analysis
from src.collector.ai_processor.siem_engine import run_siem_analysis
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/purge")
async def purge_old_data(days: int = None, db: Session = Depends(get_db)):
    """
    Purges logs and snapshots from the database.
    - If days=0: Purges ALL data.
    - If days > 0: Purges data older than X days.
    - If days is None: Uses retention_days from config.yaml.
    """
    config = load_config()
    if days is None:
        days = config.get("maintenance", {}).get("retention_days", 7)
    
    try:
        if days == 0:
            # Purge EVERYTHING
            deleted_logs = db.query(LogEntry).delete()
            deleted_snapshots = db.query(Snapshot).delete()
            message = "Purged all data from the database"
        else:
            # Purge based on date
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            deleted_logs = db.query(LogEntry).filter(LogEntry.timestamp < cutoff_date).delete()
            deleted_snapshots = db.query(Snapshot).filter(Snapshot.timestamp < cutoff_date).delete()
            message = f"Purged data older than {days} days"
        
        db.commit()
        return {
            "status": "success", 
            "message": message,
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

@router.post("/full-cycle-ai")
async def full_cycle_ai(db: Session = Depends(get_db)):
    try:
        # 1. Run Analysis
        noc_result = run_noc_analysis()
        siem_result = run_siem_analysis()
        
        # 2. Trigger Notifications (The engines already handle saving to DB)
        
        # 3. Purge Data
        purge_result = await purge_old_data(db=db)
        
        return {
            "status": "success",
            "noc": noc_result,
            "siem": siem_result,
            "purge": purge_result
        }
    except Exception as e:
        logger.error(f"Full cycle AI failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/context")
async def get_ai_context(machine: str = None, db: Session = Depends(get_db)):
    """
    Aggregates metrics and logs into a single text block for AI context.
    - machine: Optional name or IP address to filter the data.
    """
    time_threshold = datetime.utcnow() - timedelta(hours=4)
    
    # Base query for machines
    query = db.query(Machine)
    if machine:
        # Check if it's a machine name or a mapped IP
        query = query.filter(Machine.name == machine)
    
    machines = query.all()
    
    # If filtering by IP, we might need to check syslog mappings
    if not machines and machine:
        from src.collector.database import SyslogMapping
        mapping = db.query(SyslogMapping).filter(SyslogMapping.ip_address == machine).first()
        if mapping:
            machines = db.query(Machine).filter(Machine.name == mapping.machine_name).all()
    
    context = "### WIGO SYSTEM STATE (Last 4 Hours) ###\n\n"
    
    for m in machines:
        context += f"--- MACHINE: {m.name} ---\n"
        
        # Metrics Digest
        snapshots = db.query(Snapshot).filter(
            Snapshot.machine_id == m.id,
            Snapshot.timestamp >= time_threshold
        ).all()
        if snapshots:
            context += "METRICS TRENDS:\n"
            for s in snapshots:
                context += f"[{s.timestamp.isoformat()}] {json.dumps(s.metrics)}\n"
        
        # Log Entries (Top 20 most recent unique logs for context)
        logs = db.query(LogEntry).filter(
            LogEntry.machine_id == m.id,
            LogEntry.timestamp >= time_threshold
        ).order_by(LogEntry.timestamp.desc()).limit(20).all()
        
        if logs:
            context += "LOG ENTRIES:\n"
            for l in logs:
                context += f"[{l.timestamp.isoformat()}] (Count: {l.count}) {l.message}\n"
        
        context += "\n"
        
    return {"text": context}

from src.collector.database import AIAnalysis

@router.get("/last-report")
async def get_last_report(db: Session = Depends(get_db)):
    """
    Returns the last AI analysis report stored in the database.
    """
    report = db.query(AIAnalysis).order_by(AIAnalysis.timestamp.desc()).first()
    if not report:
        return {"status": "error", "message": "No reports found"}
    return report
