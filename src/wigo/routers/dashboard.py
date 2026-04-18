from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.wigo.database import get_db, Agent, Action, ActionStatus
from sqlalchemy import func

router = APIRouter()

@router.get("/dashboard/stats")
def get_stats(db: Session = Depends(get_db)):
    total_agents = db.query(Agent).count()
    active_agents = db.query(Agent).filter(Agent.status == "ACTIVE").count()
    pending_actions = db.query(Action).filter(Action.status == "PENDING").count()
    
    return {
        "total_agents": total_agents,
        "active_agents": active_agents,
        "pending_actions": pending_actions,
        "system_status": "Healthy" if active_agents > 0 else "Warning"
    }

@router.get("/dashboard/agents")
def get_agents(db: Session = Depends(get_db)):
    agents = db.query(Agent).all()
    return agents

@router.get("/dashboard/reports")
def get_reports(db: Session = Depends(get_db)):
    # Fetch recent AI actions as reports
    reports = db.query(Action).order_by(Action.created_at.desc()).limit(10).all()
    return reports
