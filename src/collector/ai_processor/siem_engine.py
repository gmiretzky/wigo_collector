from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from src.collector.database import SessionLocal, LogEntry, Machine, AIAnalysis
from src.collector.ai_processor.utils import call_ai
from src.collector.settings import load_config
from src.collector.notifications import send_notification, forward_analysis
import requests
import json

def generate_siem_digest(db, machine_id, time_threshold):
    # Top 10 most frequent logs
    top_logs = db.query(
        LogEntry.message,
        func.sum(LogEntry.count).label("total_count")
    ).filter(
        LogEntry.machine_id == machine_id,
        LogEntry.timestamp >= time_threshold
    ).group_by(LogEntry.message).order_by(text("total_count DESC")).limit(10).all()
    
    # New unique errors (seen in 4h, but not in previous 20h)
    twenty_four_hours_ago = datetime.utcnow() - timedelta(days=1)
    recent_logs = db.query(LogEntry.message).filter(
        LogEntry.machine_id == machine_id,
        LogEntry.timestamp >= time_threshold
    ).distinct().all()
    
    new_unique_errors = []
    error_keywords = ["error", "critical", "failed", "panic", "warning", "denied", "reject"]
    
    for (msg,) in recent_logs:
        is_error = any(k in msg.lower() for k in error_keywords)
        if is_error:
            exists_before = db.query(LogEntry).filter(
                LogEntry.machine_id == machine_id,
                LogEntry.message == msg,
                LogEntry.timestamp < time_threshold,
                LogEntry.timestamp >= twenty_four_hours_ago
            ).first()
            if not exists_before:
                new_unique_errors.append(msg)

    return {
        "top_frequent_logs": [{"message": l[0], "count": l[1]} for l in top_logs],
        "new_unique_errors": new_unique_errors[:10]
    }

def run_siem_analysis():
    db = SessionLocal()
    try:
        time_threshold = datetime.utcnow() - timedelta(hours=4)
        machines = db.query(Machine).all()
        
        system_log_digest = []
        for machine in machines:
            digest = generate_siem_digest(db, machine.id, time_threshold)
            if digest["top_frequent_logs"] or digest["new_unique_errors"]:
                system_log_digest.append({
                    "machine": machine.name,
                    "digest": digest
                })

        if not system_log_digest:
            return "No significant logs collected in the last 4 hours."

        prompt = f"""
        You are a SIEM (Security Information and Event Management) specialist. 
        Analyze the following security log digest for the last 4 hours.
        Identify security issues, unauthorized access attempts, or anomalies.
        
        Digest:
        {json.dumps(system_log_digest, indent=2)}
        
        CRITICAL INSTRUCTIONS:
        1. Provide a concise security health report in text.
        2. If you need more logs or command outputs to find a root cause, you MUST include a JSON block in your response.
        3. Use ONLY these JSON templates wrapped in ---TRIM---:
        
        To request more data:
        ---TRIM---
        {{"status_code": "more_data", "machine_name": "NAME", "more_data": ["cmd1", "cmd2"]}}
        ---TRIM---
        
        To trigger a notification alert:
        ---TRIM---
        {{"trigger_ha": true, "message": "SECURITY ALERT DETAILS"}}
        ---TRIM---
        """
        
        analysis = call_ai(prompt)
        
        # Save to DB
        new_analysis = AIAnalysis(
            analysis_type="SIEM",
            summary=analysis,
            raw_response=analysis
        )
        db.add(new_analysis)
        db.commit()

        # Handle JSON triggers
        if "---TRIM---" in analysis:
            try:
                parts = analysis.split("---TRIM---")
                for part in parts[1::2]:
                    data = json.loads(part.strip())
                    if data.get("status_code") == "more_data":
                        # Forward to specialized webhook
                        forward_analysis(data)
                        # Also send a notification
                        msg = f"SIEM requested more data for {data.get('machine_name')}"
                        send_notification(msg, "critical")
                    if data.get("trigger_ha"):
                        send_notification(data.get("message", "SIEM Alert"), "critical")
            except Exception as e:
                print(f"Error parsing SIEM JSON: {e}")

        return analysis

    finally:
        db.close()
