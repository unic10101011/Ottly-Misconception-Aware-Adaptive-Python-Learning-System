"""Related history is a bounded, user-owned summary of saved attempts."""
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault('DATABASE_URL', 'sqlite://')
os.environ.setdefault('JWT_SECRET', 'personalized-history-test-secret')

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.learning_submission import LearningSubmission
from app.models.user import User


def test_selects_recent_distinct_problems_and_only_safe_fields(tmp_path):
    from app.services.personalized_history import select_related_history

    engine = create_engine(f"sqlite:///{(tmp_path / 'history.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    start = datetime(2026, 10, 16, tzinfo=timezone.utc)

    def row(user, problem, minute, *, passed=False, knowledge=None, status='ready', tag='range_boundary'):
        return LearningSubmission(
            user_id=user, problem_id=problem, problem_title=problem,
            problem_description='private description', knowledge_ids=knowledge,
            code='SECRET_HISTORY_CODE', judge_json={'hidden': 'SECRET_HIDDEN'},
            analysis_json={'status': status, 'content': {
                'misconception_tag': tag, 'suspected_cause': '疑似边界没有覆盖。',
            }} if status else None,
            passed=passed, error_type='WRONG_ANSWER', hints_viewed_max=2,
            created_at=start + timedelta(minutes=minute),
        )

    with Session(engine) as db:
        db.add_all([
            row(1, 'old-a', 1, knowledge=['K06']),
            row(1, 'old-b', 2, knowledge=['K06']),
            row(1, 'old-a', 3, passed=True, knowledge=['K06']),
            row(1, 'new-a', 4, knowledge=['K06']),
            row(1, 'new-a', 5, knowledge=['K06']),
            row(1, 'new-a', 6, knowledge=['K06']),
            row(1, 'unrelated', 7, knowledge=['K02']),
            row(1, 'legacy', 8, knowledge=None),
            row(1, 'failed-analysis', 9, knowledge=['K06'], status='timeout'),
            row(1, 'unknown-tag', 10, knowledge=['K06'], tag='invented'),
            row(2, 'other-user', 11, knowledge=['K06']),
            row(1, 'current', 12, knowledge=['K06'], status='preparing'),
            row(2, 'other-current', 13, knowledge=['K06'], status='preparing'),
        ])
        db.commit()
        current_id = db.query(LearningSubmission.id).filter_by(problem_id='current').scalar()
        items = select_related_history(db, 1, current_id, ['K06'])
        assert [item['problem_id'] for item in items] == ['new-a', 'old-b', 'old-a']
        assert [item['later_passed'] for item in items] == [False, False, True]
        assert len(items) == 3
        assert set(items[0]) == {
            'problem_id', 'problem_title', 'knowledge_ids', 'error_type',
            'misconception_tag', 'suspected_cause', 'later_passed',
            'hints_viewed_max', 'created_at',
        }
        assert 'SECRET_HISTORY_CODE' not in str(items)
        assert select_related_history(db, 1, current_id, ['K99']) == []
        assert select_related_history(db, 2, current_id, ['K06']) == []
        other_current = db.query(LearningSubmission.id).filter_by(problem_id='other-current').scalar()
        other_items = select_related_history(db, 2, other_current, ['K06'])
        assert [item['problem_id'] for item in other_items] == ['other-user']
    engine.dispose()


def test_selection_and_later_passed_use_submission_time(tmp_path):
    from app.services.personalized_history import select_related_history

    engine = create_engine(f"sqlite:///{(tmp_path / 'time.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    start = datetime(2026, 10, 16, tzinfo=timezone.utc)

    def row(problem, minute, passed=False):
        return LearningSubmission(
            user_id=1, problem_id=problem, problem_title=problem,
            problem_description='', knowledge_ids=['K06'], code='private',
            judge_json={}, analysis_json={'status': 'ready', 'content': {
                'misconception_tag': 'range_boundary', 'suspected_cause': '边界可能不对。',
            }}, passed=passed, error_type='WRONG_ANSWER',
            created_at=start + timedelta(minutes=minute),
        )

    with Session(engine) as db:
        db.add_all([
            row('a', 10), row('a', 9), row('b', 8),
            row('a', 11, passed=True), row('future', 30),
            row('current', 20),
        ])
        db.commit()
        current_id = db.query(LearningSubmission.id).filter_by(problem_id='current').scalar()
        items = select_related_history(db, 1, current_id, ['K06'])
        assert [item['problem_id'] for item in items] == ['a', 'a', 'b']
        assert [item['later_passed'] for item in items] == [True, True, False]
    engine.dispose()
