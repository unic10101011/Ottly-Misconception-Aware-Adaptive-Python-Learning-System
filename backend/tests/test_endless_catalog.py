import asyncio
import json

import pytest

from test_submission import client, login
from test_endless import draft, review, saved_questions, unlock


def database():
    from main import app
    from app.core.database import get_db
    return app.dependency_overrides[get_db]()


def test_writer_preserves_versions_and_checks_owner_and_category(client):
    from app.models.user import User
    from app.services.endless import Candidate
    from app.services.endless_catalog import save_verified_problem
    login(client)
    dependency = database()
    with next(dependency) as db:
        user_id = db.query(User).filter_by(username='submission_student').one().id
        lesson = Candidate.model_validate(draft()).as_lesson()
        with pytest.raises(ValueError, match='入库格式'):
            save_verified_problem(db, user_id, lesson.model_copy(update={'kind': 'main'}), 'test')
        with pytest.raises(ValueError, match='账号不存在'):
            save_verified_problem(db, user_id + 100, lesson, 'test')
        save_verified_problem(db, user_id, lesson, 'test')
        with pytest.raises(ValueError, match='不能覆盖'):
            save_verified_problem(db, user_id, lesson, 'test')
        db.rollback()
    dependency.close()
    assert len(saved_questions()) == 1


def test_catalog_draw_includes_owned_generated_questions_without_calling_model(client, monkeypatch):
    from app.models.user import User
    from app.services import endless
    from app.services.endless_catalog import save_verified_problem
    from app.api import endless as api
    owner = login(client)
    unlock(client, owner)
    dependency = database()
    with next(dependency) as db:
        user_id = db.query(User).filter_by(username='submission_student').one().id
        lesson = endless.Candidate.model_validate(draft()).as_lesson()
        save_verified_problem(db, user_id, lesson, 'test')
    dependency.close()
    monkeypatch.setattr(endless, 'generate_candidate', lambda *args: pytest.fail('draw must not call AI'))
    monkeypatch.setattr(api.secrets, 'choice', lambda items: next(item for item in items if item.kind == 'endless'))
    selected = client.post('/api/v1/code/endless', headers=owner, json={'mode': 'catalog'}).json()['data']
    assert selected['problem_id'] == lesson.problem_id


def test_import_program_validates_and_writes_to_same_category(client, monkeypatch):
    from app.models.user import User
    from app.services import endless, error_analysis
    import app.core.database as core_database
    from write_endless_problem import import_candidate
    owner = login(client)
    unlock(client, owner)
    dependency = database()
    with next(dependency) as db:
        user_id = db.query(User).filter_by(username='submission_student').one().id
        bind = db.get_bind()
    dependency.close()
    from sqlalchemy.orm import Session
    monkeypatch.setattr(core_database, 'SessionLocal', lambda: Session(bind=bind))
    monkeypatch.setattr(error_analysis, 'analysis_configuration_error', lambda: None)
    async def audit(candidate):
        return endless.Review.model_validate(review())
    monkeypatch.setattr(endless, 'review_candidate', audit)
    problem_id = asyncio.run(import_candidate(json.dumps(draft()), user_id))
    items = client.get('/api/v1/code/practice', headers=owner).json()['data']['items']
    assert next(item for item in items if item['problem_id'] == problem_id)['category'] == 'endless'
    with pytest.raises(ValueError):
        asyncio.run(import_candidate(json.dumps(draft(knowledge_ids=['K99'])), user_id))
    with pytest.raises(ValueError):
        asyncio.run(import_candidate(json.dumps(draft(reference_solution='print(999)')), user_id))
    async def reject(candidate):
        return endless.Review.model_validate(review(approved=False, issues=['题意不一致']))
    monkeypatch.setattr(endless, 'review_candidate', reject)
    with pytest.raises(ValueError):
        asyncio.run(import_candidate(json.dumps(draft()), user_id))
    assert len(saved_questions()) == 1
