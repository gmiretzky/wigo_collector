from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.wigo.database import get_db, Agent, AgentStatus
from src.wigo.pki import pki
import datetime

router = APIRouter()

class RegistrationRequest(BaseModel):
    hostname: str
    ip_address: str
    brand: str
    company: str
    module: str
    software_version: str
    registration_token: str
    csr: str  # PEM formatted CSR

class RegistrationResponse(BaseModel):
    certificate: str
    ca_cert: str
    status: str

@router.post("/register", response_model=RegistrationResponse)
def register_agent(req: RegistrationRequest, db: Session = Depends(get_db)):
    # Check if agent is pre-registered with this token
    agent = db.query(Agent).filter(
        Agent.hostname == req.hostname,
        Agent.ip_address == req.ip_address,
        Agent.registration_token == req.registration_token,
        Agent.status == AgentStatus.PENDING
    ).first()
    
    if not agent:
        raise HTTPException(status_code=403, detail="Invalid registration token or agent not pre-registered")
    
    try:
        cert_pem, serial = pki.sign_agent_csr(req.csr, req.hostname)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to sign certificate: {str(e)}")

    agent.brand = req.brand
    agent.module = req.module
    agent.software_version = req.software_version
    agent.cert_serial = str(serial)
    agent.last_checkin = datetime.datetime.utcnow()
    agent.status = AgentStatus.ACTIVE
    # We clear the token after successful registration if we want it to be one-time
    # agent.registration_token = None 
    
    db.commit()

    with open(pki.ca_cert_path, "r") as f:
        ca_cert = f.read()

    return RegistrationResponse(
        certificate=cert_pem,
        ca_cert=ca_cert,
        status="registered"
    )
