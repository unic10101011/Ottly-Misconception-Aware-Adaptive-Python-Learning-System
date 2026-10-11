from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class ClassSelection(Base):
    __tablename__ = "class_selections"
    
    id = Column(Integer, primary_key=True, index=True)
    class_name = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())