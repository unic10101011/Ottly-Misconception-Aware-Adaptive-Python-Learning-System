from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(10), default="enabled", index=True)

class AIChatRecord(Base):
    __tablename__ = "ai_chat_records"
    
    record_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    conversation_id = Column(Integer, nullable=False)
    session_id = Column(String(255), nullable=False, index=True)
    question = Column(String(1000), nullable=False)
    question_type = Column(String(50), nullable=False)
    answer = Column(String(5000), nullable=False)
    response_time = Column(DateTime(timezone=True), server_default=func.now())
    is_stream = Column(Integer, default=0)