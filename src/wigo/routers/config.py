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

from google import genai

@router.get("/config/models")
def get_ai_models(provider: str = "gemini", db: Session = Depends(get_db)):
    """
    Fetch dynamically supported models from the AI provider.
    """
    if provider == "gemini":
        db_setting = db.query(Settings).filter(Settings.key == "ai_token").first()
        api_key = db_setting.value if db_setting else os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            return [{"id": "gemini-1.5-pro-latest", "name": "Gemini 1.5 Pro (API Key Missing)"}]
            
        try:
            client = genai.Client(api_key=api_key)
            supported_models = []
            for m in client.models.list():
                # The new SDK model object properties: name, display_name, supported_generation_methods
                methods = getattr(m, 'supported_generation_methods', [])
                if "generateContent" in methods:
                    supported_models.append({
                        "id": m.name.replace("models/", "") if m.name.startswith("models/") else m.name,
                        "name": getattr(m, 'display_name', m.name)
                    })
                    
            # Filter to relevant gemini models and return top 5
            gemini_models = [m for m in supported_models if "gemini" in m["id"].lower()]
            return gemini_models[:5] if gemini_models else supported_models[:5]
        except Exception as e:
            return [{"id": "gemini-1.5-pro-latest", "name": f"API Error: {str(e)}"}]
            
    elif provider == "ollama":
        return [
            {"id": "llama3", "name": "Llama 3"},
            {"id": "mistral", "name": "Mistral"},
            {"id": "phi3", "name": "Phi-3"}
        ]
        
    return []
