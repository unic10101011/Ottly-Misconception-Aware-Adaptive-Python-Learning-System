"""The thirteenth map stop: draw a catalog exercise or validate an AI challenge."""
import asyncio
import json
import logging
import secrets
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.coding import passed_problem_ids
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services import endless, error_analysis
from app.services.endless_catalog import endless_lessons, save_verified_problem
from app.services.problem_catalog import LEVELS, PROBLEMS, SCHEMA_VERSION

router = APIRouter()
logger = logging.getLogger(__name__)


class EndlessRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['catalog', 'ottly']


def event(stage: str, message: str = '', **data) -> str:
    return json.dumps({'code': 200, 'data': {'stage': stage, 'message': message, **data}},
                      ensure_ascii=False) + '\n'


@router.post('/code/endless')
async def start_endless(request: EndlessRequest, current_user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    user_id = current_user.id
    passed = passed_problem_ids(db, user_id)
    if len(LEVELS) != 12 or not all(slot.problem_id in passed for slot in LEVELS):
        raise HTTPException(status_code=403, detail='完成全部 12 关后解锁无尽挑战。')
    if request.mode == 'catalog':
        candidates = [item for item in [*PROBLEMS.values(), *endless_lessons(db, user_id)]
                      if item.kind in {'practice', 'endless'} and item.published
                      and set(item.prerequisite_problem_ids).issubset(passed)]
        pending = [item for item in candidates if item.problem_id not in passed]
        if not candidates:
            raise HTTPException(status_code=404, detail='题库暂时没有可用题目，请选择让 Ottly 出题。')
        selected = secrets.choice(pending or candidates)
        return {'schema_version': SCHEMA_VERSION, 'code': 200,
                'data': {'stage': 'ready', 'problem_id': selected.problem_id}}
    if error_analysis.analysis_configuration_error():
        raise HTTPException(status_code=503, detail='Ottly 出题暂不可用：请配置后端 DeepSeek API Key。')
    profile = endless.learning_profile(db, user_id)
    bind = db.get_bind()
    db.rollback()  # No transaction is held while the model generates and reviews.

    async def progress():
        try:
            async with asyncio.timeout(180):
                previous_error = ''
                for attempt in range(2):
                    yield event('generating', '正在生成候选题…' if not attempt else '正在重新生成候选题…')
                    try:
                        raw = await endless.generate_candidate(profile, previous_error)
                        yield event('structure', '正在检查题目结构…')
                        candidate = endless.Candidate.model_validate_json(raw)
                        lesson = candidate.as_lesson()
                        yield event('executing', '正在执行参考答案和测试…')
                        await run_in_threadpool(endless.validate_reference, lesson)
                        yield event('reviewing', '正在检查边界及题意一致性…')
                        review = await endless.review_candidate(candidate)
                        lesson = await run_in_threadpool(endless.validate_review, lesson, review)
                    except (ValueError, SyntaxError) as error:
                        previous_error = str(error)[:1500]
                        logger.info('Endless candidate rejected at attempt %s: %s', attempt + 1, previous_error)
                        continue
                    # Only a fully verified version is persisted; never register it globally.
                    with Session(bind=bind) as saved:
                        save_verified_problem(saved, user_id, lesson, error_analysis.analysis_model())
                    yield event('ready', '题目已通过验证。', problem_id=lesson.problem_id)
                    return
                yield event('error', '本次生成题目未通过验证，请重试或从题库中抽题。')
        except (TimeoutError, httpx.TimeoutException):
            yield event('error', '出题或验证超时，请重试或从题库中抽题。')
        except httpx.HTTPError:
            yield event('error', 'Ottly 出题服务暂不可用，请检查模型配置后重试，或从题库中抽题。')
        except Exception:
            logger.exception('Endless challenge preparation failed')
            yield event('error', '题目准备失败，请重试或从题库中抽题。')

    return StreamingResponse(progress(), media_type='application/x-ndjson', headers={
        'X-Accel-Buffering': 'no', 'Cache-Control': 'no-store',
    })
