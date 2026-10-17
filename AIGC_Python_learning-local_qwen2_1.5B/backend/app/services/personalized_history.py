"""Select small, saved learning summaries for the current user's next hint."""
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.learning_submission import LearningSubmission
from app.services.error_analysis import MISCONCEPTION_TAGS
from app.services.learning_contract import utc_iso


def select_related_history(db: Session, user_id: int, current_id: int,
                           knowledge_ids: list[str]) -> list[dict]:
    if not knowledge_ids:
        return []
    current = db.query(LearningSubmission.id, LearningSubmission.created_at).filter(
        LearningSubmission.id == current_id,
        LearningSubmission.user_id == user_id,
    ).first()
    if current is None:
        return []
    rows = db.query(
        LearningSubmission.id, LearningSubmission.problem_id, LearningSubmission.problem_title,
        LearningSubmission.knowledge_ids, LearningSubmission.error_type,
        LearningSubmission.analysis_json, LearningSubmission.passed,
        LearningSubmission.hints_viewed_max, LearningSubmission.created_at,
    ).filter(
        LearningSubmission.user_id == user_id,
        or_(LearningSubmission.created_at < current.created_at,
            and_(LearningSubmission.created_at == current.created_at,
                 LearningSubmission.id < current_id)),
    ).order_by(LearningSubmission.created_at.desc(), LearningSubmission.id.desc()).all()
    passed_after = {}
    candidates = []
    relevant_ids = set(knowledge_ids)
    for row in rows:
        if row.passed:
            passed_after.setdefault(row.problem_id, (row.created_at, row.id))
            continue
        if not row.knowledge_ids or not relevant_ids.intersection(row.knowledge_ids):
            continue
        analysis = row.analysis_json or {}
        if analysis.get('status') != 'ready':
            continue
        content = analysis.get('content') or {}
        tag = content.get('misconception_tag')
        if tag not in MISCONCEPTION_TAGS:
            continue
        candidates.append((row, tag, content.get('suspected_cause', ''),
                           passed_after.get(row.problem_id, (row.created_at, row.id))
                           > (row.created_at, row.id)))
    selected = []
    seen_problems = set()
    for candidate in candidates:
        if candidate[0].problem_id not in seen_problems:
            selected.append(candidate)
            seen_problems.add(candidate[0].problem_id)
            if len(selected) == 3:
                break
    if len(selected) < 3:
        selected.extend(candidate for candidate in candidates if candidate not in selected)
        selected = selected[:3]
    selected.sort(key=lambda candidate: (candidate[0].created_at, candidate[0].id), reverse=True)
    return [{
        'problem_id': row.problem_id,
        'problem_title': row.problem_title,
        'knowledge_ids': row.knowledge_ids,
        'error_type': row.error_type,
        'misconception_tag': tag,
        'suspected_cause': cause,
        'later_passed': later_passed,
        'hints_viewed_max': row.hints_viewed_max,
        'created_at': utc_iso(row.created_at),
    } for row, tag, cause, later_passed in selected]
