"""Prewritten understanding checks, separate from all judged code attempts."""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.coding import passed_problem_ids, require_lesson
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.guide_progress import GuideProgress
from app.models.user import User
from app.services.problem_catalog import DATA_DIR

GUIDES = json.loads((DATA_DIR / 'guides' / 'catalog.json').read_text(encoding='utf-8'))
router = APIRouter()


def load_guide(problem_id, db, user_id):
    require_lesson(problem_id, passed_problem_ids(db, user_id))
    story = GUIDES.get(problem_id)
    if story is None:
        raise HTTPException(status_code=404, detail='本题没有知识引导')
    return story


def completion_query(db, user_id, story):
    return db.query(GuideProgress).filter_by(user_id=user_id, problem_id=story['problemId'], guide_version=story['id'])


@router.get('/code/guides/{problem_id}')
def get_guide(problem_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    story = load_guide(problem_id, db, current_user.id)
    return {'code': 200, 'data': {'story': story, 'completed': completion_query(db, current_user.id, story).first() is not None}}


class GuideCompletion(BaseModel):
    version: str = Field(max_length=100)
    heard: list[str] = Field(max_length=2)
    answers: dict[str, str] = Field(max_length=3)


@router.post('/code/guides/{problem_id}/complete')
def complete_guide(problem_id: str, body: GuideCompletion, current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    story = load_guide(problem_id, db, current_user.id)
    options = {option['id'] for node in story['nodes'] if node['type'] == 'choice' for option in node['options']}
    quizzes = {node['id']: node['correct'] for node in story['nodes'] if node['type'] == 'quiz'}
    if (body.version != story['id'] or not set(body.heard).issubset(options)
            or len(set(body.heard)) < story['requiredQuestions'] or body.answers != quizzes):
        raise HTTPException(status_code=422, detail='请完整听完至少一个疑问并答对全部知识小测，再完成引导。')
    if completion_query(db, current_user.id, story).first() is None:
        db.add(GuideProgress(user_id=current_user.id, problem_id=problem_id, guide_version=story['id']))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if completion_query(db, current_user.id, story).first() is None:
                raise
    return {'code': 200, 'data': {'completed': True}}
