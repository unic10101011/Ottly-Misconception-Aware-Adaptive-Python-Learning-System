"""Only verified, immutable Ottly challenges are stored here."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String

from app.core.database import Base


class GeneratedProblem(Base):
    __tablename__ = 'generated_problems'

    problem_id = Column(String(100), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    lesson_json = Column(JSON, nullable=False)
    model = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
