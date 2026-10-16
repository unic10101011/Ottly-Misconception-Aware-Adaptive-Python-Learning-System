"""Authenticated access to a student's own judged attempts."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.learning_submission import LearningSubmission
from app.models.learning_review import LearningReview
from app.models.user import User
from app.services.submission import PROBLEMS
from app.services.problem_catalog import SCHEMA_VERSION
from app.services.learning_contract import contract_judge, submission_error, history_analysis, snapshot_fields, utc_iso


router = APIRouter()


@router.get("/code/progress")
def my_level_progress(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    passed_ids = db.query(LearningSubmission.problem_id).filter(
        LearningSubmission.user_id == current_user.id,
        LearningSubmission.passed.is_(True),
    ).distinct().all()
    return {"schema_version": SCHEMA_VERSION, "code": 200, "data": {"passed_problem_ids": [row.problem_id for row in passed_ids]}}


class HintViewRequest(BaseModel):
    level: int = Field(ge=1, le=3)


@router.get("/code/submissions")
def my_submissions(
    failed_only: bool = False,
    problem_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(LearningSubmission).filter(LearningSubmission.user_id == current_user.id)
    if failed_only:
        query = query.filter(LearningSubmission.passed.is_(False))
    if problem_id is not None:
        query = query.filter(LearningSubmission.problem_id == problem_id)
    total = query.count()
    rows = query.order_by(LearningSubmission.id.desc()).offset(offset).limit(limit).all()
    problem_ids = {row.problem_id for row in rows if not row.passed}
    later_passes = {}
    if problem_ids:
        later_passes = dict(
            db.query(LearningSubmission.problem_id, func.max(LearningSubmission.id))
            .filter(LearningSubmission.user_id == current_user.id,
                    LearningSubmission.passed.is_(True),
                    LearningSubmission.problem_id.in_(problem_ids))
            .group_by(LearningSubmission.problem_id).all()
        )
    review_sources = dict(db.query(LearningReview.submission_id, LearningReview.source_submission_id).filter(
        LearningReview.user_id == current_user.id,
        LearningReview.submission_id.in_([row.id for row in rows]),
    ).all()) if rows else {}
    items = []
    for row in rows:
        judge = contract_judge(row.judge_json, code=row.code)
        analysis = history_analysis(row, judge)
        items.append({
            **snapshot_fields(row),
            "id": row.id,
            "problem_id": row.problem_id,
            "problem_title": row.problem_title,
            "problem_description": row.problem_description,
            "code": row.code,
            "judge": judge.model_dump(mode='json'),
            "analysis": analysis.model_dump(mode='json') if analysis else None,
            "passed": row.passed,
            "error_type": submission_error(judge, row.error_type, code=row.code),
            "hints_viewed_max": row.hints_viewed_max,
            "resolved_later": not row.passed and later_passes.get(row.problem_id, 0) > row.id,
            "created_at": utc_iso(row.created_at),
            "review_source_id": review_sources.get(row.id),
        })
    return {"schema_version": SCHEMA_VERSION, "code": 200, "data": {"items": items, "total": total, "limit": limit, "offset": offset}}


@router.get("/code/mistakes")
def my_mistake_questions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    attempts = db.query(LearningSubmission).filter(
        LearningSubmission.user_id == current_user.id,
    ).order_by(LearningSubmission.id.desc()).all()
    review_ids = {row.submission_id for row in db.query(LearningReview).filter(
        LearningReview.user_id == current_user.id,
    ).all()}
    grouped = {}
    for attempt in attempts:
        grouped.setdefault(attempt.problem_id, []).append(attempt)

    items = []
    for problem_id, rows in grouped.items():
        failures = [row for row in rows if not row.passed]
        if not failures:
            continue
        reviews = [row for row in rows if row.id in review_ids]
        recent = reviews[:5]
        passed_count = sum(row.passed for row in recent)
        cause = next((analysis for row in failures
                      if (analysis := history_analysis(row, contract_judge(row.judge_json)))
                      and analysis.status == 'ready' and analysis.content), None)
        items.append({
            **snapshot_fields(rows[0]),
            "problem_id": problem_id,
            "title": rows[0].problem_title,
            "description": rows[0].problem_description,
            "source": "系统关卡" if problem_id in PROBLEMS else "来源待题库提供",
            "first_wrong_submission_id": failures[-1].id,
            "first_wrong_at": utc_iso(failures[-1].created_at),
            "latest_at": utc_iso(rows[0].created_at),
            "latest_passed": rows[0].passed,
            "last_wrong_code": failures[0].code,
            "latest_suspected_cause": cause.content.suspected_cause if cause else None,
            "attempt_count": len(rows),
            "wrong_count": len(failures),
            "review_count": len(reviews),
            "recent_review_passed": passed_count,
            "recent_review_total": len(recent),
            "review_rate_percent": round(passed_count / len(recent) * 100) if len(recent) >= 3 else None,
            "related_questions": [],
        })
    return {"schema_version": SCHEMA_VERSION, "code": 200, "data": {"items": items, "total": len(items)}}


@router.patch("/code/submissions/{submission_id}/hints")
def record_hint_view(
    submission_id: int,
    request: HintViewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(LearningSubmission).filter(
        LearningSubmission.id == submission_id,
        LearningSubmission.user_id == current_user.id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    if row.passed or not row.analysis_json or row.analysis_json.get("status") != "ready":
        raise HTTPException(status_code=409, detail="本次提交没有可查看的学习提示")
    db.query(LearningSubmission).filter(
        LearningSubmission.id == row.id,
        LearningSubmission.user_id == current_user.id,
        LearningSubmission.hints_viewed_max < request.level,
    ).update({LearningSubmission.hints_viewed_max: request.level}, synchronize_session=False)
    db.commit()
    db.refresh(row)
    return {"schema_version": SCHEMA_VERSION, "code": 200, "data": {"submission_id": row.id, "hints_viewed_max": row.hints_viewed_max}}
