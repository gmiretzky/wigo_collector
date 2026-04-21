from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.wigo.database import get_db, Agent, Action, ActionStatus
from src.wigo.ai.brain import get_brain
import uuid
import datetime

router = APIRouter()

class TelemetryBurst(BaseModel):
    hostname: str
    data: str

class ActionResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int

@router.post("/actions/telemetry")
async def receive_telemetry(burst: TelemetryBurst, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.hostname == burst.hostname).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not registered")
    
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
        
        # Trigger Notification (Placeholder - in real world would call Pushover/HA)
        # For now, we return the action ID so the user can approve via REST
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
def get_pending_actions(hostname: str, db: Session = Depends(get_db)):
    """
    Endpoint for agents to poll for instructions.
    """
    agent = db.query(Agent).filter(Agent.hostname == hostname).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not registered")
    
    pending = db.query(Action).filter(
        Action.agent_id == agent.id, 
        Action.status == ActionStatus.APPROVED
    ).all()
    
    # Format and mark as executed (or wait for agent to confirm execution)
    commands = []
    for action in pending:
        commands.append({
            "id": action.id,
            "command": action.command
        })
        # For now, auto-mark as executed when polled
        action.status = ActionStatus.EXECUTED
        action.executed_at = datetime.datetime.utcnow()
    
    db.commit()
    return {"commands": commands}

@router.post("/actions/{action_id}/result")
async def receive_action_result(action_id: int, result: ActionResult, db: Session = Depends(get_db)):
    action = db.query(Action).filter(Action.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    action.result_stdout = result.stdout
    action.result_stderr = result.stderr
    action.exit_code = result.exit_code
    action.status = ActionStatus.EXECUTED if result.exit_code == 0 else ActionStatus.FAILED
    action.executed_at = datetime.datetime.utcnow()
    
    # Process result with AI for analysis
    brain = get_brain()
    analysis = await brain.analyze_result(action.command, result.stdout, result.stderr, result.exit_code)
    action.ai_analysis = analysis
    
    db.commit()
    return {"status": "ok"}
