from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime
import enum

Base = declarative_base()

class AgentStatus(enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    OFFLINE = "offline"
    REVOKED = "revoked"

class ActionStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISPATCHED = "dispatched"
    EXECUTED = "executed"
    FAILED = "failed"

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String, index=True)
    ip_address = Column(String)
    brand = Column(String)  # e.g., MikroTik, Ubuntu
    company = Column(String)
    module = Column(String)  # e.g., local, remote-mikrotik
    software_version = Column(String)
    status = Column(Enum(AgentStatus), default=AgentStatus.PENDING)
    cert_serial = Column(String, unique=True, nullable=True)
    registration_token = Column(String, unique=True, nullable=True)
    description = Column(String, nullable=True)
    last_checkin = Column(DateTime, default=datetime.datetime.utcnow)
    metadata_json = Column(JSON)  # Store extra info

    actions = relationship("Action", back_populates="agent")

class Action(Base):
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    command = Column(String)
    rationale = Column(String)
    status = Column(Enum(ActionStatus), default=ActionStatus.PENDING)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)
    approval_token = Column(String)  # For REST callback validation
    
    result_stdout = Column(String, nullable=True)
    result_stderr = Column(String, nullable=True)
    exit_code = Column(Integer, nullable=True)
    ai_analysis = Column(String, nullable=True)
    trace_id = Column(String, index=True, nullable=True)

    agent = relationship("Agent", back_populates="actions")

class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(String)

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"))
    sender = Column(String)  # 'user', 'agent', 'ai'
    content = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    external_source = Column(String, nullable=True) # 'telegram', 'whatsapp', etc.
    trace_id = Column(String, index=True, nullable=True)

    agent = relationship("Agent")

# Database setup
DATABASE_URL = "sqlite:///./wigo.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
