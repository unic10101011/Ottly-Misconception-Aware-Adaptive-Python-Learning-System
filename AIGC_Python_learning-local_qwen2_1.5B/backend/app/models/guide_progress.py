from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from app.core.database import Base


class GuideProgress(Base):
    __tablename__ = 'guide_progress'
    __table_args__ = (UniqueConstraint('user_id', 'problem_id', 'guide_version', name='uq_guide_completion'),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    problem_id = Column(String(100), nullable=False)
    guide_version = Column(String(100), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
