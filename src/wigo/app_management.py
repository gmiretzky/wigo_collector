from fastapi import FastAPI, Request
from pathlib import Path
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from src.wigo.database import init_db
from src.wigo.routers import config, actions, registration, dashboard
import os

app = FastAPI(
    title="WIGO Management",
    description="HTTP Management Interface",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup directories
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@app.on_event("startup")
async def startup():
    init_db()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    if not (TEMPLATES_DIR / "index.html").exists():
        listing = list(TEMPLATES_DIR.iterdir()) if TEMPLATES_DIR.exists() else "DIRECTORY_MISSING"
        return HTMLResponse(
            f"<h1>Template Missing</h1><p>Path: {TEMPLATES_DIR}/index.html</p><p>Found: {listing}</p>", 
            status_code=500
        )
    return templates.TemplateResponse(request=request, name="index.html", context={})

@app.get("/health")
def health():
    return {"status": "ok", "interface": "management"}

# Include Routers
from src.wigo.routers import config, actions, registration, dashboard, chat
app.include_router(config.router, prefix="/api")
app.include_router(actions.router, prefix="/api")
app.include_router(registration.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
