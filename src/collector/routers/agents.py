from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from pydantic import BaseModel
import requests
import json

from src.collector.database import get_db, Machine, Snapshot, LogEntry
from src.collector.settings import load_config

router = APIRouter()

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

def send_notification(message: str, severity: str):
    config = load_config()
    webhooks = config.get("webhooks", {})
    
    # Pushover
    pushover = webhooks.get("pushover", {})
    if pushover.get("enabled"):
        try:
            requests.post(pushover["url"], data={
                "token": pushover["token"],
                "user": pushover["user"],
                "message": f"[{severity.upper()}] WIGO: {message}"
            }, timeout=5)
        except Exception as e:
            print(f"Failed to send Pushover notification: {e}")

    # Home Assistant
    ha = webhooks.get("homeassistant", {})
    if ha.get("enabled"):
        try:
            headers = {"Authorization": f"Bearer {ha['token']}", "Content-Type": "application/json"}
            requests.post(ha["url"], headers=headers, json={"state": message, "attributes": {"severity": severity}}, timeout=5)
        except Exception as e:
            print(f"Failed to send HA notification: {e}")

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

    # Save Logs
    for log_msg in report.logs:
        log_entry = LogEntry(
            machine_id=machine.id,
            timestamp=datetime.utcnow(),
            message=log_msg
        )
        db.add(log_entry)

    db.commit()

    # Check Thresholds for immediate alarms
    check_thresholds(report)

    return {"status": "success"}
