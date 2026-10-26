from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.coding import passed_problem_ids, require_lesson
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.learning_submission import LearningSubmission
from app.models.user import User
from app.services.sandbox.trace_runner import run_trace_process
from app.services.problem_catalog import LEVELS, PROBLEMS
from app.services import trace_sessions
from app.services.trace_explanation import explain_step

router = APIRouter(dependencies=[Depends(get_current_user)])
REPLAY_LEVELS = {slot.problem_id: slot.id for slot in LEVELS}


class TraceRequest(BaseModel):
    problem_id: str = Field(max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=6000)
    submission_id: int | None = Field(default=None, gt=0)
    stdin: str = Field(default='', max_length=2000)


@router.post('/code/execution-trace')
async def execution_trace(body: TraceRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.problem_id not in REPLAY_LEVELS:
        raise HTTPException(status_code=422, detail='执行回放仅支持正式12关。')
    if (body.code is None) == (body.submission_id is None):
        raise HTTPException(status_code=422, detail='请选择当前代码或已提交版本，两者不能同时提供。')
    stdin = body.stdin
    if body.problem_id == 'shell-total-v1':
        raw = stdin.strip() or '3'
        if not raw.isascii() or not raw.isdecimal() or len(raw) > 3 or not 0 <= int(raw) <= 100:
            raise HTTPException(status_code=422, detail='第8关演示输入需要是0～100的一个整数。')
        stdin = raw + '\n'
    elif body.problem_id == 'level1':
        stdin = ''
    elif stdin and not stdin.endswith('\n'):
        stdin += '\n'
    code = body.code
    if body.submission_id is not None:
        saved = db.query(LearningSubmission).filter_by(id=body.submission_id, user_id=current_user.id,
                                                      problem_id=body.problem_id).first()
        if saved is None:
            raise HTTPException(status_code=404, detail='找不到属于当前账号的这次提交。')
        code = saved.code
    if len(code) > 6000:
        raise HTTPException(status_code=422, detail='首版回放只支持6000字符以内的代码。')
    require_lesson(body.problem_id, passed_problem_ids(db, current_user.id))
    data = await run_in_threadpool(run_trace_process, code, stdin, supports_text=body.problem_id != 'shell-total-v1',
                                   supports_structures=REPLAY_LEVELS[body.problem_id] in {11, 12})
    data.update(problem_id=body.problem_id, submission_id=body.submission_id, code=code,
                problem_title=f'第 {REPLAY_LEVELS[body.problem_id]} 关 · {PROBLEMS[body.problem_id].title}',
                code_source='submission' if body.submission_id is not None else 'draft', stdin=stdin,
                test_case_label=('本题无需输入（演示不代表全部正式测试）' if body.problem_id == 'level1'
                                 else f'自选演示输入 n={stdin.strip()}（不代表全部正式测试）' if body.problem_id == 'shell-total-v1'
                                 else '使用下方演示输入（不代表全部正式测试）'))
    trace_id = trace_sessions.remember_trace(current_user.id, data)
    return {'code': 200, 'data': {**data, 'trace_id': trace_id}}


class ExplanationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    step_index: int = Field(ge=0, lt=300)


@router.post('/code/execution-trace/{trace_id}/explanation')
async def trace_explanation(trace_id: str, body: ExplanationRequest, current_user: User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    session = trace_sessions.owned_trace(trace_id, current_user.id)
    data = session.data
    require_lesson(data['problem_id'], passed_problem_ids(db, current_user.id))
    index = body.step_index
    if index >= len(data['steps']):
        raise HTTPException(422, '这一步没有实际执行快照，无法解释。')
    async with session.lock:
        if index in session.answers:
            return {'code': 200, 'data': {**session.answers[index], 'cached': True}}
        answer = await explain_step(PROBLEMS[data['problem_id']], data, index)
        trace_sessions.cache_answer(session, index, answer)
        return {'code': 200, 'data': {**answer, 'cached': False}}
