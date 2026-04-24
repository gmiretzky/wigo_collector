from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.wigo.database import get_db, Agent, Action, ActionStatus
from src.wigo.ai.brain import get_brain
import uuid
import datetime

import hmac
import hashlib
import time

router = APIRouter()

class TelemetryBurst(BaseModel):
    hostname: str
    data: str
    timestamp: int
    hmac_signature: str

class ActionResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    timestamp: int
    hmac_signature: str

def verify_agent_hmac(agent: Agent, msg_parts: list, signature: str) -> bool:
    if not agent.registration_token:
        return False
    msg = "".join(str(p) for p in msg_parts)
    expected = hmac.new(agent.registration_token.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

def check_timestamp(ts: int):
    if abs(int(time.time()) - ts) > 300:
        raise HTTPException(status_code=403, detail="Request expired")

@router.post("/actions/telemetry")
async def receive_telemetry(burst: TelemetryBurst, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.hostname == burst.hostname).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not registered")
    
    # Validate HMAC
    check_timestamp(burst.timestamp)
    if not verify_agent_hmac(agent, [burst.hostname, burst.timestamp], burst.hmac_signature):
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")

    # Process with AI
    brain = get_brain()
    proposal = await brain.process_telemetry(agent.id, burst.data)
    
    if proposal.get("issue_detected"):
        # Create a pending action
        new_action = Action(
            agent_id=agent.id,
            command=proposal.get("proposed_command"),
            rationale=proposal.get("rationale"),
            status=ActionStatus.PENDING,
            approval_token=str(uuid.uuid4())
        )
        db.add(new_action)
        db.commit()
        db.refresh(new_action)
        
        return {
            "status": "action_proposed",
            "action_id": new_action.id,
            "rationale": new_action.rationale,
            "command": new_action.command,
            "approval_url": f"/api/actions/{new_action.id}/approve?token={new_action.approval_token}"
        }
    
    return {"status": "ok", "message": "No action required"}

@router.post("/actions/{action_id}/approve")
def approve_action(action_id: int, token: str, db: Session = Depends(get_db)):
    action = db.query(Action).filter(Action.id == action_id, Action.approval_token == token).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found or invalid token")
    
    action.status = ActionStatus.APPROVED
    db.commit()
    return {"status": "approved"}

@router.post("/actions/{action_id}/reject")
def reject_action(action_id: int, token: str, db: Session = Depends(get_db)):
    action = db.query(Action).filter(Action.id == action_id, Action.approval_token == token).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found or invalid token")
    
    action.status = ActionStatus.REJECTED
    db.commit()
    return {"status": "rejected"}

@router.get("/actions/pending")
def get_pending_actions(hostname: str, timestamp: int, hmac_signature: str, db: Session = Depends(get_db)):
    """
    Endpoint for agents to poll for instructions.
    """
    agent = db.query(Agent).filter(Agent.hostname == hostname).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not registered")
    
    # Validate HMAC
    check_timestamp(timestamp)
    if not verify_agent_hmac(agent, [hostname, timestamp], hmac_signature):
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")

    pending = db.query(Action).filter(
        Action.agent_id == agent.id, 
        Action.status == ActionStatus.APPROVED
    ).all()
    
    commands = []
    for action in pending:
        commands.append({
            "id": action.id,
            "command": action.command
        })
        action.status = ActionStatus.EXECUTED
        action.executed_at = datetime.datetime.utcnow()
    
    db.commit()
    return {"commands": commands}

@router.post("/actions/{action_id}/result")
async def receive_action_result(action_id: int, result: ActionResult, db: Session = Depends(get_db)):
    action = db.query(Action).filter(Action.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    agent = action.agent
    # Validate HMAC
    check_timestamp(result.timestamp)
    if not verify_agent_hmac(agent, [action_id, result.timestamp], result.hmac_signature):
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")

    action.result_stdout = result.stdout
    action.result_stderr = result.stderr
    action.exit_code = result.exit_code
    action.status = ActionStatus.EXECUTED if result.exit_code == 0 else ActionStatus.FAILED
    action.executed_at = datetime.datetime.utcnow()
    
    brain = get_brain()
    analysis = await brain.analyze_result(action.command, result.stdout, result.stderr, result.exit_code)
    action.ai_analysis = analysis
    
    db.commit()
    return {"status": "ok"}
