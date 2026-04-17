from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from src.collector.database import SessionLocal, LogEntry, Machine, AIAnalysis
from src.collector.ai_processor.utils import call_ai
from src.collector.settings import load_config
from src.collector.notifications import send_notification
import requests
import json

def run_siem_analysis():
    db = SessionLocal()
    try:
        # Get data from the last 4 hours
        time_threshold = datetime.utcnow() - timedelta(hours=4)
        machines = db.query(Machine).all()
        
        log_data = []
        for machine in machines:
            entries = db.query(LogEntry).filter(
                LogEntry.machine_id == machine.id,
                LogEntry.timestamp >= time_threshold
            ).all()
            
            if entries:
                machine_logs = {
                    "machine": machine.name,
                    "logs": [e.message for e in entries]
                }
                log_data.append(machine_logs)

        if not log_data:
            return "No logs collected in the last 4 hours."

        prompt = f"""
        You are a SIEM (Security Information and Event Management) specialist. 
        Analyze the following logs collected over the last 4 hours.
        Identify security issues, unauthorized access attempts, or anomalies.
        
        Logs:
        {json.dumps(log_data, indent=2)}
        
        Provide a concise security report. 
        If you find critical security issues, format a JSON object at the end of your response like this:
        ---TRIM---
        {{"trigger_ha": true, "message": "Security Alert details here"}}
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

        # Check for HA trigger
        if "---TRIM---" in analysis:
            try:
                parts = analysis.split("---TRIM---")
                trigger_data = json.loads(parts[1].strip())
                if trigger_data.get("trigger_ha"):
                    send_notification(trigger_data.get("message", "SIEM Alert Found"), "critical")
            except:
                pass

        return analysis

    finally:
        db.close()
