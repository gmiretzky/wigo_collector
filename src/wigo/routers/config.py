from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
import os
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.wigo.database import get_db, Settings
from src.wigo.pki import CA_DIR
from typing import Dict

router = APIRouter()

@router.post("/config/certs/upload")
async def upload_custom_certs(
    ca_cert: UploadFile = File(...),
    ca_key: UploadFile = File(...)
):
    """
    Allow uploading existing valid certificates to be used as the Root CA.
    """
    try:
        ca_cert_content = await ca_cert.read()
        ca_key_content = await ca_key.read()
        
        # Save to the CA directory
        with open(os.path.join(CA_DIR, "rootCA.pem"), "wb") as f:
            f.write(ca_cert_content)
        with open(os.path.join(CA_DIR, "rootCA.key"), "wb") as f:
            f.write(ca_key_content)
            
        return {"status": "success", "message": "Custom certificates uploaded and active."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save certificates: {str(e)}")

@router.post("/config/settings")
def update_settings(settings: Dict[str, str], db: Session = Depends(get_db)):
    for key, value in settings.items():
        db_setting = db.query(Settings).filter(Settings.key == key).first()
        if db_setting:
            db_setting.value = value
        else:
            db_setting = Settings(key=key, value=value)
            db.add(db_setting)
    db.commit()
    return {"status": "success"}

@router.get("/config/settings")
def get_settings(db: Session = Depends(get_db)):
    settings = db.query(Settings).all()
    return {s.key: s.value for s in settings}

@router.get("/config/certs/ca")
def get_ca_cert():
    """
    Public endpoint to get the Root CA certificate so agents can trust it.
    """
    ca_path = os.path.join(CA_DIR, "rootCA.pem")
    if not os.path.exists(ca_path):
        raise HTTPException(status_code=404, detail="CA certificate not found.")
    
    with open(ca_path, "r") as f:
        return {"ca_cert": f.read()}
