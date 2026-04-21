from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.wigo.database import get_db, Agent, Action, ActionStatus, AgentStatus
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional
import secrets
import string

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

class PreRegisterRequest(BaseModel):
    hostname: str
    ip_address: str
    brand: str
    company: str
    module: str
    software_version: str
    description: Optional[str] = None

@router.post("/dashboard/pre-register")
def pre_register_agent(req: PreRegisterRequest, db: Session = Depends(get_db)):
    # Generate a random token
    alphabet = string.ascii_letters + string.digits
    token = ''.join(secrets.choice(alphabet) for _ in range(16))
    
    new_agent = Agent(
        hostname=req.hostname,
        ip_address=req.ip_address,
        brand=req.brand,
        company=req.company,
        module=req.module,
        software_version=req.software_version,
        description=req.description,
        registration_token=token,
        status=AgentStatus.PENDING
    )
    db.add(new_agent)
    db.commit()
    
    return {"token": token}

@router.get("/dashboard/history")
def get_action_history(db: Session = Depends(get_db)):
    actions = db.query(Action).order_by(Action.created_at.desc()).all()
    # Format for UI
    history = []
    for action in actions:
        history.append({
            "id": action.id,
            "agent_hostname": action.agent.hostname if action.agent else "Unknown",
            "command": action.command,
            "rationale": action.rationale,
            "status": action.status,
            "executed_at": action.executed_at,
            "result_stdout": action.result_stdout,
            "result_stderr": action.result_stderr,
            "exit_code": action.exit_code,
            "ai_analysis": action.ai_analysis
        })
    return history
