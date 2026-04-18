from fastapi import FastAPI
from src.wigo.database import init_db
from src.wigo.routers import actions
import ssl
import os
from src.wigo.pki import pki

app = FastAPI(
    title="WIGO Agent API",
    description="HTTPS mTLS Agent Interface",
    version="2.0.0"
)

@app.on_event("startup")
async def startup():
    init_db()
    pki.ensure_ca()

@app.get("/health")
def health():
    return {"status": "ok", "interface": "agent-api"}

# Include Routers for Agents
# Only include telemetry, polling, and chat
from src.wigo.routers import actions, chat
app.include_router(actions.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

def get_ssl_context():
    if not os.path.exists(pki.ca_cert_path):
        pki.ensure_ca()
    
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(certfile=pki.ca_cert_path, keyfile=pki.ca_key_path)
    ctx.load_verify_locations(cafile=pki.ca_cert_path)
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx
