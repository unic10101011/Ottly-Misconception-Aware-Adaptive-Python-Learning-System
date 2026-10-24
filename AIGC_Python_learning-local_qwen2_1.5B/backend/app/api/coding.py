import logging
import json
from time import perf_counter

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.learning_submission import LearningSubmission
from app.models.learning_review import LearningReview
from app.models.user import User
from pydantic import BaseModel, Field
from app.services.sandbox.runner import run_code_process
from app.services.submission import CaseResult, PROBLEMS, JudgeResult, SubmissionRequest, judge_submission, public_judge
from app.services.error_analysis import AnalysisResult, analyze_failure
from app.services.lesson_feedback import with_lesson_hints
from app.services.personalized_history import select_related_history
from app.services.problem_catalog import SCHEMA_VERSION, LEVELS, KNOWLEDGE, Problem, TestCase
from app.services.learning_contract import (
    ContractJudge, ContractAnalysis, contract_judge, contract_analysis,
    submission_error, analysis_knowledge_scope, error_code, history_analysis, utc_iso,
)

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


class CodeRunRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20000, description="Python code to execute")
    timeout: int = Field(default=10, ge=1, le=10, description="Execution timeout in seconds")
    stdin: str = Field(default='', max_length=8000)
    problem_id: str | None = Field(default=None, max_length=100)


class CodeRunResponse(BaseModel):
    schema_version: str = SCHEMA_VERSION
    code: int = 200
    msg: str = "执行成功"
    data: dict = {}


@router.post("/code/run")
async def execute_code(request: CodeRunRequest, current_user: User = Depends(get_current_user),
                       db: Session = Depends(get_db), stream_analysis: bool = False):
    lesson = (require_lesson(request.problem_id, passed_problem_ids(db, current_user.id))
              if request.problem_id else None)
    result = await run_in_threadpool(run_code_process, request.code, timeout=request.timeout, stdin=request.stdin)
    if any(error['type'] == 'RunnerError' for error in result['errors']):
        raise HTTPException(status_code=503, detail='执行器暂不可用，请稍后重试')

    data = {
            "success": result["success"],
            "output": result["output"],
            "output_available": result["output_available"],
            "errors": [{**error, 'type': error_code(error['type'], code=request.code)} for error in result['errors']],
            "execution_time": result["execution_time"],
    }
    if not result['success']:
        # Analyze this actual execution once, without creating a submission.
        test = TestCase(case_id='run', stdin=request.stdin, expected_output='')
        problem = (lesson.execution_problem().model_copy(update={'tests': [test]}) if lesson else Problem(
            problem_id='python-run', title='Python 代码运行', description='解释当前输入下的实际运行错误。',
            tests=[test], comparison='exact'))
        judge = JudgeResult(
            status='timeout' if any(error['type'] == '超时警告' for error in result['errors']) else 'execution_error',
            passed=False, passed_cases=0, total_cases=1,
            cases=[CaseResult(case_id='run', passed=False, expected_output='', actual_output=result['output'],
                              output_available=result['output_available'], errors=result['errors'],
                              execution_time=result['execution_time'])],
        )
        data['judge'] = contract_judge(judge, code=request.code).model_dump(mode='json')
        scope = analysis_knowledge_scope(lesson) if lesson else []

        async def finish_analysis():
            try:
                analysis = await analyze_failure(problem, request.code, judge, execution_mode='run')
            except Exception:
                logger.exception('Run analysis failed; execution result remains available')
                analysis = AnalysisResult(status='unavailable', message='AI 分析暂不可用，运行结果已保留。')
            data['analysis'] = contract_analysis(analysis, scope).model_dump(mode='json')

        if stream_analysis:
            async def progress():
                data['analysis'] = contract_analysis(AnalysisResult(status='preparing', message='Ottly正在分析错因'), scope).model_dump(mode='json')
                yield json.dumps({'code': 200, 'data': data}, ensure_ascii=False) + '\n'
                await finish_analysis()
                yield json.dumps({'code': 200, 'data': data}, ensure_ascii=False) + '\n'

            return StreamingResponse(progress(), media_type='application/x-ndjson', headers={
                'X-Accel-Buffering': 'no', 'Cache-Control': 'no-store',
            })
        await finish_analysis()
    return CodeRunResponse(msg="执行成功" if result["success"] else "代码有错误", data=data)


class SubmissionData(BaseModel):
    submission_id: int
    problem_id: str
    version: int
    created_at: str
    error_type: str | None
    judge: ContractJudge
    analysis: ContractAnalysis
    timings: dict[str, float]


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


@router.get('/code/practice')
def practice_questions(level_no: int | None = Query(default=None, ge=1, le=12),
                       current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    passed = passed_problem_ids(db, current_user.id)
    items = [{
        'problem_id': problem.problem_id, 'level_no': problem.level_no,
        'kind': problem.kind, 'title': problem.title, 'practice_focus': problem.practice_focus,
        'knowledge_ids': problem.knowledge_ids, 'completed': problem.problem_id in passed,
        'available': problem.published and set(problem.prerequisite_problem_ids).issubset(passed),
    } for problem in PROBLEMS.values()
        if problem.kind == 'practice' and problem.published
        and (level_no is None or problem.level_no == level_no)]
    items.sort(key=lambda item: (item['level_no'], item['problem_id']))
    return {'schema_version': SCHEMA_VERSION, 'code': 200, 'data': {'items': items}}


@router.get('/code/problems/{problem_id}')
def lesson(problem_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    passed = passed_problem_ids(db, current_user.id)
    problem = require_lesson(problem_id, passed)
    # Explicit allowlist: never include private tests, hints or solutions here.
    data = problem.model_dump(include={
        'schema_version', 'problem_id', 'version', 'level_no', 'kind', 'practice_focus',
        'title', 'difficulty', 'knowledge_ids',
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
    main_error = submission_error(judge, code=request.code)
    # Keep the model input in its original shape; normalize only public responses.
    model_judge = public_judge(judge)
    judge = contract_judge(model_judge, code=request.code)
    raw_analysis = (AnalysisResult(status='skipped', message='测试已通过，无需 AI 分析。') if judge.passed
                    else AnalysisResult(status='preparing', message='正在准备提示'))
    analysis = contract_analysis(raw_analysis, analysis_knowledge_scope(problem))
    timings = {'judge_ms': judge_ms, 'model_load_ms': 0.0, 'hint_generation_ms': 0.0}
    analysis.timings = timings
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
        judge_json=model_judge.model_dump(mode="json"),
        analysis_json={**analysis.model_dump(mode="json"), 'timings': timings},
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
    logger.info('submission_timing submission_id=%s judge_ms=%.2f model_load_ms=0 hint_generation_ms=0',
                record.id, judge_ms)
    return SubmissionResponse(data=SubmissionData(
        submission_id=record.id, problem_id=problem.problem_id, version=record.problem_version,
        created_at=utc_iso(record.created_at), error_type=record.error_type,
        judge=judge, analysis=analysis, timings=timings,
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
        analysis = history_analysis(record, contract_judge(record.judge_json, code=record.code))
        return {'schema_version': SCHEMA_VERSION, 'code': 200, 'data': {
            'submission_id': record.id, 'analysis': analysis.model_dump(mode='json') if analysis else None,
            'timings': record.analysis_json.get('timings', {}),
        }}
    problem = PROBLEMS.get(record.problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail='题目不存在')
    model_judge = JudgeResult.model_validate(record.judge_json)
    started = perf_counter()
    try:
        related_history = select_related_history(db, current_user.id, record.id, record.knowledge_ids or [])
        raw_analysis = await analyze_failure(problem.execution_problem(), record.code, model_judge,
                                             related_history=related_history)
    except Exception:
        logger.exception('Teaching analysis failed; judged submission %s remains saved', submission_id)
        raw_analysis = AnalysisResult(status='unavailable', message='教学分析暂不可用，判题和提交记录已保存。')
    raw_analysis = with_lesson_hints(problem, raw_analysis, model_judge)
    hint_ms = round((perf_counter() - started) * 1000, 2)
    analysis = contract_analysis(raw_analysis, analysis_knowledge_scope(problem))
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
    timings['model_load_ms'] = raw_analysis.model_load_ms
    analysis.timings = timings
    saved_record.analysis_json = {**analysis.model_dump(mode='json'), 'timings': timings}
    db.commit()
    logger.info('submission_timing submission_id=%s judge_ms=%.2f model_load_ms=%.2f hint_generation_ms=%.2f',
                submission_id, timings.get('judge_ms', 0), timings['model_load_ms'], hint_ms)
    return {'schema_version': SCHEMA_VERSION, 'code': 200, 'data': {
        'submission_id': submission_id, 'analysis': analysis.model_dump(mode='json'), 'timings': timings,
    }}
