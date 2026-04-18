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
    csr: str  # PEM formatted CSR

class RegistrationResponse(BaseModel):
    certificate: str
    ca_cert: str
    status: str

@router.post("/register", response_model=RegistrationResponse)
def register_agent(req: RegistrationRequest, db: Session = Depends(get_db)):
    # Check if agent already exists
    existing_agent = db.query(Agent).filter(Agent.hostname == req.hostname).first()
    
    # In a production environment, we might want a manual approval or a token
    # For now, we'll auto-approve and sign.
    
    try:
        cert_pem, serial = pki.sign_agent_csr(req.csr, req.hostname)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to sign certificate: {str(e)}")

    if existing_agent:
        existing_agent.ip_address = req.ip_address
        existing_agent.brand = req.brand
        existing_agent.company = req.company
        existing_agent.module = req.module
        existing_agent.software_version = req.software_version
        existing_agent.cert_serial = str(serial)
        existing_agent.last_checkin = datetime.datetime.utcnow()
        existing_agent.status = AgentStatus.ACTIVE
    else:
        new_agent = Agent(
            hostname=req.hostname,
            ip_address=req.ip_address,
            brand=req.brand,
            company=req.company,
            module=req.module,
            software_version=req.software_version,
            cert_serial=str(serial),
            status=AgentStatus.ACTIVE
        )
        db.add(new_agent)
    
    db.commit()

    with open(pki.ca_cert_path, "r") as f:
        ca_cert = f.read()

    return RegistrationResponse(
        certificate=cert_pem,
        ca_cert=ca_cert,
        status="registered"
    )
