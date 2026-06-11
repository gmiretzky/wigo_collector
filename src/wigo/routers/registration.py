from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.wigo.database import get_db, Agent, AgentStatus
from src.wigo.pki import pki
from src.wigo.routers.actions import _consume_nonce
from src.wigo.rate_limit import limiter
import datetime

import hmac
import hashlib
import time

router = APIRouter()

class RegistrationRequest(BaseModel):
    hostname: str
    ip_address: str
    brand: str
    company: str
    module: str
    software_version: str
    registration_token: str
    timestamp: int
    nonce: str
    hmac_signature: str

class RegistrationResponse(BaseModel):
    status: str
    message: str

def verify_hmac(key: str, message: str, signature: str) -> bool:
    expected = hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

@router.post("/register", response_model=RegistrationResponse)
@limiter.limit("5/minute")
def register_agent(request: Request, req: RegistrationRequest, db: Session = Depends(get_db)):
    # 1. Check if agent is pre-registered with this token
    # We only filter by token and status to be more robust to hostname/IP differences
    agent = db.query(Agent).filter(
        Agent.registration_token == req.registration_token,
        Agent.status == AgentStatus.PENDING
    ).first()
    
    if not agent:
        raise HTTPException(status_code=403, detail="Invalid registration token or agent not pre-registered")
    
    # 2. Check timestamp freshness
    now = int(time.time())
    if abs(now - req.timestamp) > 300:
        raise HTTPException(status_code=403, detail="Request expired (timestamp mismatch)")

    # 3. Consume nonce (replay prevention)
    _consume_nonce(req.nonce)

    # 4. Verify HMAC signature — message includes nonce
    msg = f"{req.hostname}{req.ip_address}{req.timestamp}{req.nonce}"
    if not verify_hmac(req.registration_token, msg, req.hmac_signature):
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")

    # 5. Update Agent status and info
    agent.hostname = req.hostname
    agent.ip_address = req.ip_address
    agent.brand = req.brand
    agent.module = req.module
    agent.software_version = req.software_version
    agent.last_checkin = datetime.datetime.utcnow()
    agent.status = AgentStatus.ACTIVE
    
    db.commit()

    return RegistrationResponse(
        status="registered",
        message="Agent successfully registered via HMAC authentication"
    )
