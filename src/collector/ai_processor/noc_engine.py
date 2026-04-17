from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from src.collector.database import SessionLocal, Snapshot, Machine, AIAnalysis
from src.collector.ai_processor.utils import call_ai
from src.collector.settings import load_config
import requests
import json

def run_noc_analysis():
    db = SessionLocal()
    try:
        # Get data from the last 4 hours
        time_threshold = datetime.utcnow() - timedelta(hours=4)
        machines = db.query(Machine).all()
        
        system_state = []
        for machine in machines:
            snapshots = db.query(Snapshot).filter(
                Snapshot.machine_id == machine.id,
                Snapshot.timestamp >= time_threshold
            ).all()
            
            if snapshots:
                machine_data = {
                    "name": machine.name,
                    "metrics_history": [s.metrics for s in snapshots]
                }
                system_state.append(machine_data)

        if not system_state:
            return "No data collected in the last 4 hours."

        prompt = f"""
        You are a NOC (Network Operations Center) specialist. 
        Analyze the following system metrics collected over the last 4 hours.
        Identify trends, bottlenecks, or potential future failures.
        
        Data:
        {json.dumps(system_state, indent=2, default=str)}
        
        Provide a concise 'State of the Union' report. 
        If you find critical trends, format a JSON object at the end of your response like this:
        ---TRIM---
        {{"trigger_ha": true, "message": "Insight details here"}}
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

        # Check for HA trigger
        if "---TRIM---" in analysis:
            try:
                parts = analysis.split("---TRIM---")
                trigger_data = json.loads(parts[1].strip())
                if trigger_data.get("trigger_ha"):
                    # Trigger HA notification logic here
                    pass 
            except:
                pass

        return analysis

    finally:
        db.close()
