from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from src.collector.settings import load_config, save_config

router = APIRouter()

@router.get("/")
async def get_current_config():
    return load_config()

@router.post("/")
async def update_config(new_config: Dict[str, Any]):
    try:
        save_config(new_config)
        return {"status": "success", "message": "Configuration updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/thresholds")
async def get_thresholds():
    config = load_config()
    return config.get("thresholds", [])

@router.post("/thresholds")
async def set_thresholds(thresholds: List[Dict[str, Any]]):
    config = load_config()
    config["thresholds"] = thresholds
    save_config(config)
    return {"status": "success"}

@router.get("/webhooks")
async def get_webhooks():
    config = load_config()
    return config.get("webhooks", {})

@router.post("/webhooks")
async def set_webhooks(webhooks: Dict[str, Any]):
    config = load_config()
    config["webhooks"] = webhooks
    save_config(config)
    return {"status": "success"}

# Syslog Mappings
from fastapi import Depends
from sqlalchemy.orm import Session
from src.collector.database import get_db, SyslogMapping

@router.get("/syslog-mappings")
async def get_syslog_mappings(db: Session = Depends(get_db)):
    return db.query(SyslogMapping).all()

@router.post("/syslog-mappings")
async def add_syslog_mapping(mapping: Dict[str, str], db: Session = Depends(get_db)):
    # mapping: {"ip_address": "...", "machine_name": "..."}
    ip = mapping.get("ip_address")
    name = mapping.get("machine_name")
    
    existing = db.query(SyslogMapping).filter(SyslogMapping.ip_address == ip).first()
    if existing:
        existing.machine_name = name
    else:
        new_mapping = SyslogMapping(ip_address=ip, machine_name=name)
        db.add(new_mapping)
    
    db.commit()
    return {"status": "success"}
