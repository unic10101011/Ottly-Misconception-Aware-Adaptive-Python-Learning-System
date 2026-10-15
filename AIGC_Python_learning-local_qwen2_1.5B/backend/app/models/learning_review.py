"""Marks submissions made from the mistake review page."""
from sqlalchemy import Column, ForeignKey, Integer

from app.core.database import Base


class LearningReview(Base):
    __tablename__ = "learning_reviews"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    submission_id = Column(Integer, ForeignKey("learning_submissions.id"), nullable=False, unique=True)
    source_submission_id = Column(Integer, ForeignKey("learning_submissions.id"), nullable=False)
