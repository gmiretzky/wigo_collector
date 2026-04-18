import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'wigo.db'))
# Ensure the directory exists (it should, based on our setup, but good practice)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Machine(Base):
    __tablename__ = "machines"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    last_seen = Column(DateTime, default=datetime.utcnow)

class Snapshot(Base):
    __tablename__ = "snapshots"
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    metrics = Column(JSON) # Store list of metrics
    
class LogEntry(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    message = Column(String)
    source = Column(String, default="agent") # 'agent' or 'syslog'
    count = Column(Integer, default=1)

class SyslogMapping(Base):
    __tablename__ = "syslog_mappings"
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String, unique=True, index=True)
    machine_name = Column(String)

class AIAnalysis(Base):
    __tablename__ = "ai_analysis"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    analysis_type = Column(String) # 'NOC' or 'SIEM'
    summary = Column(String)
    raw_response = Column(String)

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Manual migration for 'source' column in 'logs' table
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('logs')]
    if 'source' not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE logs ADD COLUMN source VARCHAR DEFAULT 'agent'"))
            conn.commit()
    if 'count' not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE logs ADD COLUMN count INTEGER DEFAULT 1"))
            conn.commit()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
