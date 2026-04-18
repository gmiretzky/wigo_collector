from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from src.collector.database import SessionLocal, Snapshot, Machine, AIAnalysis
from src.collector.ai_processor.utils import call_ai
from src.collector.settings import load_config
from src.collector.notifications import send_notification, forward_analysis
import requests
import json

def calculate_metrics_digest(snapshots):
    digest = {}
    for s in snapshots:
        for m in s.metrics:
            obj = m["object"]
            val = m["value"]
            if obj not in digest:
                digest[obj] = {"min": val, "max": val, "sum": val, "count": 1, "unit": m["unit"]}
            else:
                digest[obj]["min"] = min(digest[obj]["min"], val)
                digest[obj]["max"] = max(digest[obj]["max"], val)
                digest[obj]["sum"] += val
                digest[obj]["count"] += 1
    
    final_digest = {}
    for obj, stats in digest.items():
        final_digest[obj] = {
            "min": stats["min"],
            "max": stats["max"],
            "avg": round(stats["sum"] / stats["count"], 2),
            "unit": stats["unit"]
        }
    return final_digest

def run_noc_analysis():
    db = SessionLocal()
    try:
        time_threshold = datetime.utcnow() - timedelta(hours=4)
        machines = db.query(Machine).all()
        
        system_digest = []
        for machine in machines:
            snapshots = db.query(Snapshot).filter(
                Snapshot.machine_id == machine.id,
                Snapshot.timestamp >= time_threshold
            ).all()
            
            if snapshots:
                machine_digest = {
                    "machine": machine.name,
                    "metrics_digest": calculate_metrics_digest(snapshots)
                }
                system_digest.append(machine_digest)

        if not system_digest:
            return "No data collected in the last 4 hours."

        prompt = f"""
        You are a NOC (Network Operations Center) specialist. 
        Analyze the following system health digest for the last 4 hours.
        Identify trends, bottlenecks, or potential future failures.
        
        Digest:
        {json.dumps(system_digest, indent=2, default=str)}
        
        CRITICAL INSTRUCTIONS:
        1. Provide a concise 'State of the Union' health report in text.
        2. If you need more details to find a root cause, you MUST include a JSON block in your response.
        3. Use ONLY these JSON templates wrapped in ---TRIM---:
        
        To request more data:
        ---TRIM---
        {{"status_code": "more_data", "machine_name": "NAME", "more_data": ["cmd1", "cmd2"]}}
        ---TRIM---
        
        To trigger a notification alert:
        ---TRIM---
        {{"trigger_ha": true, "message": "DETAILS"}}
        ---TRIM---
        """
        
        analysis = call_ai(prompt)
        
        # Save to DB
        new_analysis = AIAnalysis(
            analysis_type="NOC",
            summary=analysis,
            raw_response=analysis
        )
        db.add(new_analysis)
        db.commit()

        # Handle JSON triggers
        if "---TRIM---" in analysis:
            try:
                parts = analysis.split("---TRIM---")
                # Handle multiple JSONs if present
                for part in parts[1::2]:
                    data = json.loads(part.strip())
                    if data.get("status_code") == "more_data":
                        # Forward to specialized webhook
                        forward_analysis(data)
                        # Also send a notification
                        msg = f"AI requested more data for {data.get('machine_name')}"
                        send_notification(msg, "info")
                    if data.get("trigger_ha"):
                        send_notification(data.get("message", "NOC Insight"), "info")
            except Exception as e:
                print(f"Error parsing AI JSON: {e}")

        return analysis

    finally:
        db.close()
