from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List
from pydantic import BaseModel
import requests
import json

from src.collector.database import get_db, Machine, Snapshot, LogEntry
from src.collector.settings import load_config
from src.collector.notifications import send_notification

router = APIRouter()

def should_filter_log(message: str) -> bool:
    """Filter out routine info logs to save space and AI tokens."""
    routine_patterns = ["User logged in", "session opened", "session closed", "New session", "Removed session"]
    for pattern in routine_patterns:
        if pattern.lower() in message.lower():
            return True
    return False

def process_logs(db: Session, machine_id: int, log_messages: List[str], source="agent"):
    for msg in log_messages:
        if should_filter_log(msg):
            continue
            
        # Deduplication logic: Check if same log exists for this machine in entire history
        existing_log = db.query(LogEntry).filter(
            LogEntry.machine_id == machine_id,
            LogEntry.message == msg,
            LogEntry.source == source
        ).first()
        
        if existing_log:
            existing_log.count += 1
            existing_log.timestamp = datetime.utcnow()
        else:
            new_log = LogEntry(
                machine_id=machine_id, 
                message=msg, 
                source=source,
                timestamp=datetime.utcnow(),
                count=1
            )
            db.add(new_log)

class MetricSchema(BaseModel):
    object: str
    value: float
    unit: str
    status: str

class AgentReport(BaseModel):
    machine_name: str
    timestamp: str
    metrics: List[MetricSchema]
    logs: List[str]

def check_thresholds(report: AgentReport):
    config = load_config()
    thresholds = config.get("thresholds", [])
    
    for metric in report.metrics:
        for threshold in thresholds:
            if metric.object.lower() == threshold["metric"].lower():
                condition = threshold["condition"]
                value = threshold["value"]
                is_triggered = False
                
                if condition == ">" and metric.value > value:
                    is_triggered = True
                elif condition == "<" and metric.value < value:
                    is_triggered = True
                elif condition == "==" and metric.value == value:
                    is_triggered = True
                
                if is_triggered:
                    msg = f"{report.machine_name}: {metric.object} is {metric.value}{metric.unit} ({condition} {value})"
                    send_notification(msg, threshold["severity"])

@router.post("/report")
async def receive_report(report: AgentReport, db: Session = Depends(get_db)):
    # Get or create machine
    machine = db.query(Machine).filter(Machine.name == report.machine_name).first()
    if not machine:
        machine = Machine(name=report.machine_name)
        db.add(machine)
        db.commit()
        db.refresh(machine)
    else:
        machine.last_seen = datetime.utcnow()
        db.commit()

    # Save Snapshot
    snapshot = Snapshot(
        machine_id=machine.id,
        timestamp=datetime.fromisoformat(report.timestamp.replace("Z", "+00:00")),
        metrics=[m.dict() for m in report.metrics]
    )
    db.add(snapshot)

    # Process and Save Logs (Deduplicated)
    process_logs(db, machine.id, report.logs)

    db.commit()

    # Check Thresholds for immediate alarms
    check_thresholds(report)

    return {"status": "success"}
