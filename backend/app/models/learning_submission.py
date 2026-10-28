"""One row per judged code submission, owned by an existing user."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text

from app.core.database import Base


class LearningSubmission(Base):
    __tablename__ = "learning_submissions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    problem_id = Column(String(100), nullable=False, index=True)
    problem_title = Column(String(255), nullable=False)
    problem_description = Column(Text, nullable=False)
    # Nullable only for records created before the contract migration.
    schema_version = Column(String(20), nullable=True)
    problem_version = Column(Integer, nullable=True)
    difficulty = Column(Integer, nullable=True)
    knowledge_ids = Column(JSON, nullable=True)
    code = Column(Text, nullable=False)
    judge_json = Column(JSON, nullable=False)
    analysis_json = Column(JSON, nullable=True)
    passed = Column(Boolean, nullable=False)
    error_type = Column(String(80), nullable=True)
    hints_viewed_max = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
