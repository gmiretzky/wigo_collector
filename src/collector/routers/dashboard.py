from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any
from datetime import datetime, timedelta

from src.collector.database import get_db, Machine, Snapshot, LogEntry, AIAnalysis

router = APIRouter()

@router.get("/summary")
async def get_dashboard_summary(db: Session = Depends(get_db)):
    machines = db.query(Machine).all()
    result = []
    
    for machine in machines:
        # Get latest snapshot
        latest_snapshot = db.query(Snapshot).filter(Snapshot.machine_id == machine.id).order_by(Snapshot.timestamp.desc()).first()
        
        # Get recent logs (last 10)
        recent_logs = db.query(LogEntry).filter(LogEntry.machine_id == machine.id).order_by(LogEntry.timestamp.desc()).limit(10).all()
        
        result.append({
            "id": machine.id,
            "name": machine.name,
            "last_seen": machine.last_seen,
            "latest_metrics": latest_snapshot.metrics if latest_snapshot else [],
            "recent_logs": [log.message for log in recent_logs]
        })
        
    return result

@router.get("/ai-insights")
async def get_ai_insights(db: Session = Depends(get_db)):
    insights = db.query(AIAnalysis).order_by(AIAnalysis.timestamp.desc()).limit(5).all()
    return insights

@router.get("/logs/stats")
async def get_log_stats(db: Session = Depends(get_db)):
    total_count = db.query(LogEntry).count()
    
    per_machine = db.query(
        Machine.name, 
        func.count(LogEntry.id).label("count"),
        func.sum(func.length(LogEntry.message)).label("size")
    ).join(LogEntry).group_by(Machine.name).all()
    
    per_source = db.query(
        LogEntry.source,
        func.count(LogEntry.id).label("count")
    ).group_by(LogEntry.source).all()
    
    return {
        "total_count": total_count,
        "machines": [{"name": m[0], "count": m[1], "size_bytes": m[2] or 0} for m in per_machine],
        "sources": {s[0]: s[1] for s in per_source}
    }
