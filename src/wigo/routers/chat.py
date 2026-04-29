from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.wigo.database import get_db, ChatMessage, Agent
from typing import List, Optional
import datetime

router = APIRouter()

class MessageCreate(BaseModel):
    agent_id: int
    content: str
    sender: str = "user" # user, agent, ai
    external_source: Optional[str] = None # telegram, whatsapp

class MessageSchema(BaseModel):
    id: int
    agent_id: int
    sender: str
    content: str
    timestamp: datetime.datetime
    external_source: Optional[str]

    class Config:
        from_attributes = True

import uuid
from src.wigo.database import get_db, ChatMessage, Agent, Action, ActionStatus
from src.wigo.utils.logging import log_c2

@router.post("/chat/send", response_model=MessageSchema)
async def send_message(msg: MessageCreate, db: Session = Depends(get_db)):
    """
    Send a message from the management interface or remote source to an agent.
    If the sender is 'user', automatically create an Action for the agent to poll.
    """
    agent = db.query(Agent).filter(Agent.id == msg.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    trace_id = str(uuid.uuid4())
    
    db_msg = ChatMessage(
        agent_id=msg.agent_id,
        content=msg.content,
        sender=msg.sender,
        external_source=msg.external_source,
        trace_id=trace_id
    )
    db.add(db_msg)
    
    # Bridge to Action Queue
    if msg.sender == "user":
        # 1. Use AI to translate intent to action for this specific agent
        brain = get_brain()
        # We pass only this agent to the AI to force it to target it
        agent_list = [{"hostname": agent.hostname, "brand": agent.brand, "description": agent.description}]
        proposed_actions = await brain.intent_to_actions(msg.content, agent_list)
        
        if not proposed_actions:
            # Check if AI actually failed or just returned nothing
            if not brain.is_available():
                # Notify user that AI is down
                ai_warning = ChatMessage(
                    agent_id=agent.id,
                    content="⚠️ AI Intent-to-Action engine is unavailable (GEMINI_API_KEY missing). Running raw command instead.",
                    sender="ai",
                    trace_id=trace_id
                )
                db.add(ai_warning)
            
            # Fallback to raw command
            new_action = Action(
                agent_id=agent.id,
                command=msg.content,
                rationale=f"Direct command from {msg.sender}",
                status=ActionStatus.APPROVED,
                trace_id=trace_id
            )
            db.add(new_action)
            log_c2("INFO", trace_id, f"Created Raw Action {new_action.id} for {agent.hostname}")
        else:
            for pa in proposed_actions:
                # Ensure it targets the right agent (AI should, but we verify)
                target_agent = db.query(Agent).filter(Agent.hostname == pa['agent_hostname']).first()
                if not target_agent:
                    target_agent = agent # Default to current agent
                command_str = pa.get('command', pa.get('parameters', '')).strip()
                perm_level = get_permission_level(target_agent.brand, command_str)
                
                new_action = Action(
                    agent_id=target_agent.id,
                    command=command_str,
                    rationale=pa['rationale'],
                    ai_reasoning=pa['reasoning'],
                    status=ActionStatus.APPROVED if perm_level == 1 else ActionStatus.PENDING,
                    permission_level=perm_level,
                    trace_id=trace_id,
                    approval_token=str(uuid.uuid4()) if perm_level == 2 else None
                )
                db.add(new_action)
                log_audit(msg.content, pa['reasoning'], target_agent.hostname, command_str)
                log_c2("INFO", trace_id, f"Translated Intent -> Action {new_action.id} for {target_agent.hostname}")
    
    db.commit()
    db.refresh(db_msg)
    return db_msg

@router.get("/chat/messages/{agent_id}", response_model=List[MessageSchema])
def get_messages(agent_id: int, db: Session = Depends(get_db)):
    """
    Fetch message history for a specific agent.
    """
    messages = db.query(ChatMessage).filter(ChatMessage.agent_id == agent_id).order_by(ChatMessage.timestamp.asc()).all()
    return messages

class GlobalMessageCreate(BaseModel):
    content: str
    sender: str = "user"
    external_source: Optional[str] = None

from src.wigo.ai.brain import get_brain
from src.wigo.config import get_permission_level
from src.wigo.utils.logging import log_audit

@router.post("/chat/global")
async def send_global_message(msg: GlobalMessageCreate, db: Session = Depends(get_db)):
    """
    Global Intent-to-Action handler.
    Translates user text into actions across multiple agents.
    """
    trace_id = str(uuid.uuid4())
    
    # 1. Get all active agents
    agents = db.query(Agent).filter(Agent.status == "active").all()
    agent_list = [
        {"hostname": a.hostname, "brand": a.brand, "description": a.description} 
        for a in agents
    ]
    
    # 2. Query AI for actions
    brain = get_brain()
    if not brain.is_available():
        raise HTTPException(status_code=503, detail="AI Intent-to-Action engine is unavailable (GEMINI_API_KEY missing)")
        
    proposed_actions = await brain.intent_to_actions(msg.content, agent_list)
    
    results = []
    for pa in proposed_actions:
        agent = db.query(Agent).filter(Agent.hostname == pa['agent_hostname']).first()
        if not agent:
            continue
            
        # 3. Validate and Determine Permission Level
        command_str = pa['parameters']
        perm_level = get_permission_level(agent.brand, command_str)
        
        # 4. Create Action
        new_action = Action(
            agent_id=agent.id,
            command=command_str,
            rationale=pa['rationale'],
            ai_reasoning=pa['reasoning'],
            status=ActionStatus.APPROVED if perm_level == 1 else ActionStatus.PENDING,
            permission_level=perm_level,
            trace_id=trace_id,
            approval_token=str(uuid.uuid4()) if perm_level == 2 else None
        )
        db.add(new_action)
        
        # 5. Log to Audit
        log_audit(msg.content, pa['reasoning'], agent.hostname, pa['parameters'])
        log_c2("INFO", trace_id, f"Global Intent -> Action {new_action.command} for {agent.hostname} (Level {perm_level})")
        
        results.append({
            "agent": agent.hostname,
            "command": new_action.command,
            "status": new_action.status.value,
            "rationale": new_action.rationale
        })
    
    # Also log the user message to the global chat history (if we had one, but we use agent-specific for now)
    # For now, we don't have a global ChatMessage table, so we just return the results.
    
    db.commit()
    return {"trace_id": trace_id, "actions": results}

@router.post("/chat/receive")
def receive_message(msg: MessageCreate, db: Session = Depends(get_db)):
    """
    Endpoint for agents to post messages back to the controller.
    """
    db_msg = ChatMessage(
        agent_id=msg.agent_id,
        content=msg.content,
        sender="agent"
    )
    db.add(db_msg)
    db.commit()
    return {"status": "received"}
