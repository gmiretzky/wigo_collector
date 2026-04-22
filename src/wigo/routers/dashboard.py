from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.wigo.database import get_db, Agent, Action, ActionStatus, AgentStatus
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional
import secrets
import string
import re
import os

IP_REGEX = r"^(((?!25?[6-9])[12]\d|[1-9])?\d\.?\b){4}$"

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

@router.get("/dashboard/agent-types")
def get_agent_types():
    """
    Dynamically discover agent types by listing subdirectories in the 'agents' folder.
    """
    agents_dir = "agents"
    if not os.path.exists(agents_dir):
        return ["Ubuntu", "MikroTik", "Proxmox"] # Fallback
    
    # Return all subdirectories as agent types
    return [d for d in os.listdir(agents_dir) if os.path.isdir(os.path.join(agents_dir, d))]

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
    # 1. Validate IP format
    if not re.match(IP_REGEX, req.ip_address):
        raise HTTPException(status_code=400, detail="Invalid IP address format (must be 0-255 per octet)")

    # 2. Check for duplicate IP
    existing = db.query(Agent).filter(Agent.ip_address == req.ip_address).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Agent with IP {req.ip_address} already exists")

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

@router.delete("/dashboard/agents/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Delete associated actions/history first to avoid FK constraints
    db.query(Action).filter(Action.agent_id == agent_id).delete()
    db.delete(agent)
    db.commit()
    return {"status": "success", "message": "Agent removed"}

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
