from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.wigo.database import get_db, Agent, Action, ActionStatus, ChatMessage
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

from src.wigo.utils.logging import log_c2
import json

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
        log_c2("WARNING", None, f"Auth Failure: Invalid HMAC from {hostname}")
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")

    pending = db.query(Action).filter(
        Action.agent_id == agent.id, 
        Action.status == ActionStatus.APPROVED
    ).all()
    
    commands = []
    for action in pending:
        trace_id = action.trace_id or str(uuid.uuid4())
        action.trace_id = trace_id # Backfill if missing
        
        log_c2("INFO", trace_id, f"Dispatching Action {action.id} ({action.command}) to {hostname}")
        
        commands.append({
            "id": action.id,
            "command": action.command,
            "trace_id": trace_id
        })
        action.status = ActionStatus.DISPATCHED
        action.executed_at = datetime.datetime.utcnow()
    
    db.commit()
    return {"commands": commands}

from fastapi import BackgroundTasks

async def run_ai_analysis(action_id: int, command: str, stdout: str, stderr: str, exit_code: int):
    # This runs in the background
    from src.wigo.database import SessionLocal
    db = SessionLocal()
    try:
        brain = get_brain()
        analysis = await brain.analyze_result(command, stdout, stderr, exit_code)
        
        action = db.query(Action).filter(Action.id == action_id).first()
        if action:
            action.ai_analysis = analysis
            db.commit()
    finally:
        db.close()

@router.post("/actions/{action_id}/result")
async def receive_action_result(action_id: int, result: ActionResult, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    action = db.query(Action).filter(Action.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    agent = action.agent
    trace_id = action.trace_id
    
    # Validate HMAC
    check_timestamp(result.timestamp)
    if not verify_agent_hmac(agent, [action_id, result.timestamp], result.hmac_signature):
        log_c2("WARNING", trace_id, f"Result Auth Failure: Invalid HMAC for Action {action_id}")
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")

    log_c2("DEBUG", trace_id, f"Received Result for {action_id}: exit={result.exit_code}")
    
    action.result_stdout = result.stdout
    action.result_stderr = result.stderr
    action.exit_code = result.exit_code
    action.status = ActionStatus.EXECUTED if result.exit_code == 0 else ActionStatus.FAILED
    action.executed_at = datetime.datetime.utcnow()
    
    # If this was a chat command, post the result back to chat as the 'agent'
    if action.trace_id:
        chat_msg = ChatMessage(
            agent_id=agent.id,
            content=f"Result: {result.stdout[:500]}{'...' if len(result.stdout) > 500 else ''}",
            sender="agent",
            trace_id=trace_id
        )
        db.add(chat_msg)

    # Queue AI Analysis in background
    background_tasks.add_task(
        run_ai_analysis, 
        action.id, 
        action.command, 
        result.stdout, 
        result.stderr, 
        result.exit_code
    )
    
    db.commit()
    return {"status": "ok"}
