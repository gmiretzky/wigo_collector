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
        orm_mode = True

@router.post("/chat/send", response_model=MessageSchema)
def send_message(msg: MessageCreate, db: Session = Depends(get_db)):
    """
    Send a message from the management interface or remote source to an agent.
    """
    agent = db.query(Agent).filter(Agent.id == msg.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    db_msg = ChatMessage(
        agent_id=msg.agent_id,
        content=msg.content,
        sender=msg.sender,
        external_source=msg.external_source
    )
    db.add(db_msg)
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
