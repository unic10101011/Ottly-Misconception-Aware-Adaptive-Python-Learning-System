import logging
from time import perf_counter

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
from app.services.submission import PROBLEMS, GREETING, GREETING_ID, JudgeResult, SubmissionRequest, judge_submission, public_judge
from app.services.error_analysis import AnalysisResult, analyze_failure, fixed_syntax_analysis

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


class CodeRunRequest(BaseModel):
    code: str = Field(..., max_length=20000, description="Python code to execute")
    timeout: int = Field(default=10, ge=1, le=10, description="Execution timeout in seconds")
    stdin: str = Field(default='', max_length=8000)


class CodeRunResponse(BaseModel):
    code: int = 200
    msg: str = "执行成功"
    data: dict = {}


@router.post("/code/run")
def execute_code(request: CodeRunRequest):
    result = run_code_process(request.code, timeout=request.timeout, stdin=request.stdin)

    return CodeRunResponse(
        code=200,
        msg="执行成功" if result["success"] else "代码有错误",
        data={
            "success": result["success"],
            "output": result["output"],
            "output_available": result["output_available"],
            "errors": result["errors"],
            "execution_time": result["execution_time"],
        },
    )


class SubmissionData(BaseModel):
    submission_id: int
    problem_id: str
    judge: JudgeResult
    analysis: AnalysisResult
    timings: dict[str, float]


class SubmissionResponse(BaseModel):
    code: int = 200
    data: SubmissionData


def passed_problem_ids(db: Session, user_id: int) -> set[str]:
    return {row[0] for row in db.query(LearningSubmission.problem_id).filter(
        LearningSubmission.user_id == user_id, LearningSubmission.passed.is_(True),
        LearningSubmission.problem_id.in_(['level1', GREETING_ID]),
    ).distinct().all()}


@router.get('/code/levels')
def levels(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    passed = passed_problem_ids(db, current_user.id)
    return {'code': 200, 'data': {'items': [
        {'id': 1, 'problem_id': 'level1', 'name': '初识小海獭', 'published': True,
         'status': 'completed' if 'level1' in passed else 'current'},
        {'id': 2, 'problem_id': GREETING_ID, 'name': GREETING['title'], 'published': True,
         'status': 'completed' if GREETING_ID in passed else 'current' if 'level1' in passed else 'locked'},
        {'id': 3, 'problem_id': None, 'name': '贝壳小商店', 'published': False,
         'status': 'current' if GREETING_ID in passed else 'locked'},
    ]}}


@router.get('/code/problems/{problem_id}')
def lesson(problem_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if problem_id != GREETING_ID:
        raise HTTPException(status_code=404, detail='题目尚未开放')
    passed = passed_problem_ids(db, current_user.id)
    if 'level1' not in passed:
        raise HTTPException(status_code=403, detail='请先通过第 1 关')
    # Explicit allowlist: never include private tests, hints or solutions here.
    data = {key: GREETING[key] for key in (
        'problem_id', 'version', 'level_no', 'title', 'knowledge_ids',
        'prerequisite_knowledge_ids', 'description', 'story', 'teaching',
        'starter_code', 'examples',
    )}
    data['completed'] = GREETING_ID in passed
    return {'code': 200, 'data': data}


@router.get('/code/problems/{problem_id}/solution')
def solution(problem_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if problem_id != GREETING_ID:
        raise HTTPException(status_code=404, detail='题目不存在')
    if GREETING_ID not in passed_problem_ids(db, current_user.id):
        raise HTTPException(status_code=403, detail='通过本关后可查看参考解')
    return {'code': 200, 'data': {key: GREETING[key] for key in ('reference_solution', 'solution_explanation')}}


@router.post("/code/submit", response_model=SubmissionResponse)
async def submit_code(request: SubmissionRequest, current_user: User = Depends(get_current_user),
                      db: Session = Depends(get_db),
                      review_source_id: int | None = Header(default=None, alias="X-Review-Source-Id")):
    problem = PROBLEMS.get(request.problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    user_id = current_user.id
    if request.problem_id == GREETING_ID and 'level1' not in passed_problem_ids(db, user_id):
        raise HTTPException(status_code=403, detail='请先通过第 1 关')
    if review_source_id is not None:
        source = db.query(LearningSubmission).filter(
            LearningSubmission.id == review_source_id,
            LearningSubmission.user_id == user_id,
            LearningSubmission.problem_id == request.problem_id,
            LearningSubmission.passed.is_(False),
        ).first()
        if source is None:
            raise HTTPException(status_code=404, detail="复习来源错题不存在")
    judge_started = perf_counter()
    judge = await run_in_threadpool(judge_submission, problem, request.code)
    judge_ms = round((perf_counter() - judge_started) * 1000, 2)
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
    first_error = next((error.type for case in judge.cases for error in case.errors), None)
    judge = public_judge(judge)
    analysis = (AnalysisResult(status='skipped', message='测试已通过，无需 AI 分析。') if judge.passed
                else fixed_syntax_analysis(problem, request.code, judge)
                or AnalysisResult(status='preparing', message='正在准备提示'))
    timings = {'judge_ms': judge_ms, 'model_load_ms': 0.0, 'hint_generation_ms': 0.0}
    record = LearningSubmission(
        user_id=user_id,
        problem_id=problem.problem_id,
        problem_title=problem.title,
        problem_description=problem.description,
        code=request.code,
        judge_json=judge.model_dump(mode="json"),
        analysis_json={**analysis.model_dump(mode="json"), 'timings': timings},
        passed=judge.passed,
        error_type=None if judge.passed else first_error or judge.status,
    )
    db.add(record)
    db.flush()
    if review_source_id is not None:
        db.add(LearningReview(user_id=user_id, submission_id=record.id,
                              source_submission_id=review_source_id))
    db.commit()
    db.refresh(record)
    logger.info('submission_timing submission_id=%s judge_ms=%.2f model_load_ms=0 hint_generation_ms=0',
                record.id, judge_ms)
    return SubmissionResponse(data=SubmissionData(
        submission_id=record.id, problem_id=problem.problem_id, judge=judge, analysis=analysis, timings=timings
    ))


@router.post('/code/submissions/{submission_id}/analysis')
async def prepare_analysis(submission_id: int, current_user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    record = db.query(LearningSubmission).filter(
        LearningSubmission.id == submission_id,
        LearningSubmission.user_id == current_user.id,
    ).first()
    if record is None:
        raise HTTPException(status_code=404, detail='提交记录不存在')
    if record.analysis_json and record.analysis_json.get('status') != 'preparing':
        return {'code': 200, 'data': {'submission_id': record.id,
                                      'analysis': AnalysisResult.model_validate(record.analysis_json).model_dump(mode='json'),
                                      'timings': record.analysis_json.get('timings', {})}}
    problem = PROBLEMS.get(record.problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail='题目不存在')
    judge = JudgeResult.model_validate(record.judge_json)
    started = perf_counter()
    analysis = await analyze_failure(problem, record.code, judge)
    hint_ms = round((perf_counter() - started) * 1000, 2)
    user_id = current_user.id
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
    timings = dict((saved_record.analysis_json or {}).get('timings', {}))
    timings['hint_generation_ms'] = hint_ms
    timings['model_load_ms'] = analysis.model_load_ms
    saved_record.analysis_json = {**analysis.model_dump(mode='json'), 'timings': timings}
    db.commit()
    logger.info('submission_timing submission_id=%s judge_ms=%.2f model_load_ms=%.2f hint_generation_ms=%.2f',
                submission_id, timings.get('judge_ms', 0), timings['model_load_ms'], hint_ms)
    return {'code': 200, 'data': {'submission_id': submission_id, 'analysis': analysis, 'timings': timings}}
