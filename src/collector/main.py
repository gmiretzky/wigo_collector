from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from src.collector.database import init_db
import os

# Create the app
app = FastAPI(
    title="WIGO API",
    description="What Is Going On - Monitoring System API",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB on startup
@app.on_event("startup")
def on_startup():
    init_db()
    from src.collector.ai_processor.scheduler import start_scheduler
    start_scheduler()
    from src.collector.syslog_server import start_syslog_server
    start_syslog_server()

@app.on_event("shutdown")
def on_shutdown():
    from src.collector.ai_processor.scheduler import stop_scheduler
    stop_scheduler()

# Include Routers
from src.collector.routers import agents, config, dashboard, maintenance
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(maintenance.router, prefix="/api/maintenance", tags=["maintenance"])

# Serve static files and templates
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/health")
def health_check():
    return {"status": "ok"}
