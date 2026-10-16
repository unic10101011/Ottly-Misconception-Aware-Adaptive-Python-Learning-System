import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.learning_submission import LearningSubmission
from app.models.learning_review import LearningReview
from app.models.user import User
from pydantic import BaseModel, Field
from app.services.sandbox.runner import run_code_process
from app.services.submission import PROBLEMS, SubmissionRequest, judge_submission, public_judge
from app.services.error_analysis import AnalysisResult, analyze_failure
from app.services.problem_catalog import SCHEMA_VERSION, LEVELS, KNOWLEDGE
from app.services.learning_contract import (
    ContractJudge, ContractAnalysis, contract_judge, contract_analysis,
    submission_error, analysis_knowledge_scope, error_code, utc_iso,
)

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


class CodeRunRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20000, description="Python code to execute")
    timeout: int = Field(default=10, ge=1, le=10, description="Execution timeout in seconds")
    stdin: str = Field(default='', max_length=8000)


class CodeRunResponse(BaseModel):
    schema_version: str = SCHEMA_VERSION
    code: int = 200
    msg: str = "执行成功"
    data: dict = {}


@router.post("/code/run")
def execute_code(request: CodeRunRequest):
    result = run_code_process(request.code, timeout=request.timeout, stdin=request.stdin)
    if any(error['type'] == 'RunnerError' for error in result['errors']):
        raise HTTPException(status_code=503, detail='执行器暂不可用，请稍后重试')

    return CodeRunResponse(
        code=200,
        msg="执行成功" if result["success"] else "代码有错误",
        data={
            "success": result["success"],
            "output": result["output"],
            "output_available": result["output_available"],
            "errors": [{**error, 'type': error_code(error['type'], code=request.code)} for error in result['errors']],
            "execution_time": result["execution_time"],
        },
    )


class SubmissionData(BaseModel):
    submission_id: int
    problem_id: str
    version: int
    created_at: str
    error_type: str | None
    judge: ContractJudge
    analysis: ContractAnalysis


class SubmissionResponse(BaseModel):
    schema_version: str = SCHEMA_VERSION
    code: int = 200
    data: SubmissionData


def passed_problem_ids(db: Session, user_id: int) -> set[str]:
    return {row[0] for row in db.query(LearningSubmission.problem_id).filter(
        LearningSubmission.user_id == user_id, LearningSubmission.passed.is_(True),
    ).distinct().all()}


def require_lesson(problem_id, passed, *, review=False):
    problem = PROBLEMS.get(problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail='题目不存在')
    if review:
        return problem
    if not problem.published:
        raise HTTPException(status_code=403, detail='题目尚未开放')
    if not set(problem.prerequisite_problem_ids).issubset(passed):
        raise HTTPException(status_code=403, detail='请先完成前置关卡')
    return problem


@router.get('/code/levels')
def levels(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    passed = passed_problem_ids(db, current_user.id)
    items = []
    for slot in LEVELS:
        problem = PROBLEMS.get(slot.problem_id)
        prerequisites = problem.prerequisite_problem_ids if problem else slot.prerequisite_problem_ids
        items.append({
            'id': slot.id, 'problem_id': slot.problem_id, 'name': problem.title if problem else slot.name,
            'published': problem.published if problem else False,
            'status': 'completed' if slot.problem_id in passed else 'current' if set(prerequisites).issubset(passed) else 'locked',
        })
    return {'schema_version': SCHEMA_VERSION, 'code': 200, 'data': {'items': items}}


@router.get('/code/knowledge')
def knowledge_dictionary():
    return {'schema_version': SCHEMA_VERSION, 'code': 200, 'data': {'items': [
        item.model_dump(exclude={'aliases'}) for item in KNOWLEDGE.values()
    ]}}


@router.get('/code/problems/{problem_id}')
def lesson(problem_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    passed = passed_problem_ids(db, current_user.id)
    problem = require_lesson(problem_id, passed)
    # Explicit allowlist: never include private tests, hints or solutions here.
    data = problem.model_dump(include={
        'schema_version', 'problem_id', 'version', 'level_no', 'title', 'difficulty', 'knowledge_ids',
        'prerequisite_knowledge_ids', 'prerequisite_problem_ids', 'description', 'story', 'teaching',
        'starter_code', 'examples', 'comparison', 'time_limit_seconds', 'output_limit_chars',
    })
    data['completed'] = problem_id in passed
    return {'schema_version': SCHEMA_VERSION, 'code': 200, 'data': data}


@router.get('/code/problems/{problem_id}/solution')
def solution(problem_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    problem = PROBLEMS.get(problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail='题目不存在')
    passed = passed_problem_ids(db, current_user.id)
    if problem_id not in passed:
        raise HTTPException(status_code=403, detail='通过本关后可查看参考解')
    if not problem.published:
        raise HTTPException(status_code=403, detail='题目尚未开放')
    return {'schema_version': SCHEMA_VERSION, 'code': 200, 'data': problem.model_dump(include={
        'problem_id', 'version', 'reference_solution', 'solution_explanation',
    })}


@router.post("/code/submit", response_model=SubmissionResponse)
async def submit_code(request: SubmissionRequest, current_user: User = Depends(get_current_user),
                      db: Session = Depends(get_db),
                      review_source_id: int | None = Header(default=None, alias="X-Review-Source-Id")):
    problem = PROBLEMS.get(request.problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    user_id = current_user.id
    if review_source_id is not None:
        source = db.query(LearningSubmission).filter(
            LearningSubmission.id == review_source_id,
            LearningSubmission.user_id == user_id,
            LearningSubmission.problem_id == request.problem_id,
            LearningSubmission.passed.is_(False),
        ).first()
        if source is None:
            raise HTTPException(status_code=404, detail="复习来源错题不存在")
    require_lesson(request.problem_id, passed_problem_ids(db, current_user.id), review=review_source_id is not None)
    judge = await run_in_threadpool(judge_submission, problem, request.code)
    if any(error.type == 'RunnerError' for case in judge.cases for error in case.errors):
        raise HTTPException(status_code=503, detail='执行器暂不可用，请稍后重试；本次不计为学习失败')
    owner = db.query(User).filter(User.id == user_id, User.status == "enabled").with_for_update().first()
    if owner is None:
        db.rollback()
        raise HTTPException(status_code=401, detail="账号已注销，本次提交未保存")
    if review_source_id is not None:
        source = db.query(LearningSubmission).filter(
            LearningSubmission.id == review_source_id,
            LearningSubmission.user_id == user_id,
            LearningSubmission.problem_id == request.problem_id,
            LearningSubmission.passed.is_(False),
        ).first()
        if source is None:
            db.rollback()
            raise HTTPException(status_code=404, detail="复习来源错题不存在")
    main_error = submission_error(judge, code=request.code)
    # The model retains exactly its original execution/problem shapes and error names.
    model_judge = public_judge(judge)
    judge = contract_judge(judge, code=request.code)
    record = LearningSubmission(
        user_id=user_id,
        problem_id=problem.problem_id,
        problem_title=problem.title,
        problem_description=problem.description,
        schema_version=SCHEMA_VERSION,
        problem_version=problem.version,
        difficulty=problem.difficulty,
        knowledge_ids=list(problem.knowledge_ids),
        code=request.code,
        judge_json=judge.model_dump(mode="json"),
        passed=judge.passed,
        error_type=main_error,
    )
    db.add(record)
    db.flush()
    if review_source_id is not None:
        db.add(LearningReview(user_id=user_id, submission_id=record.id,
                              source_submission_id=review_source_id))
    db.commit()
    db.refresh(record)
    submission_id = record.id
    try:
        analysis = await analyze_failure(problem.execution_problem(), request.code, model_judge)
    except Exception:
        logger.exception('Teaching analysis failed; judged submission %s remains saved', submission_id)
        analysis = AnalysisResult(status='unavailable', message='教学分析暂不可用，判题和提交记录已保存。')
    analysis = contract_analysis(analysis, analysis_knowledge_scope(problem))
    owner = db.query(User).filter(User.id == user_id, User.status == "enabled").with_for_update().first()
    if owner is None:
        db.rollback()
        raise HTTPException(status_code=401, detail="账号已注销，本次提交记录已删除")
    saved_record = db.query(LearningSubmission).filter(
        LearningSubmission.id == submission_id,
        LearningSubmission.user_id == user_id,
    ).with_for_update().first()
    if saved_record is None:
        db.rollback()
        raise HTTPException(status_code=401, detail="账号已注销，本次提交记录已删除")
    saved_record.analysis_json = analysis.model_dump(mode="json")
    db.commit()
    return SubmissionResponse(data=SubmissionData(
        submission_id=submission_id, problem_id=problem.problem_id, version=saved_record.problem_version,
        created_at=utc_iso(saved_record.created_at), error_type=saved_record.error_type, judge=judge, analysis=analysis
    ))
