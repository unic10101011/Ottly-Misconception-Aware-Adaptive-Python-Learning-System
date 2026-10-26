# ==================== 完整的 ai.py ====================
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import AIChatRecord
from pydantic import BaseModel, Field
import json
import uuid
from datetime import datetime
from typing import List, Optional
from app.core.auth import get_current_user
from app.models.user import User
import httpx
from app.services import error_analysis

router = APIRouter()

# Shared DeepSeek-V4.1-Flash configuration for all AI features.
MAX_TOKENS = 450
CHAT_CONTEXT_TOKENS = 8192
CHAT_MAX_TURNS = 20
CHAT_RUNTIME_ID = str(uuid.uuid4())
active_chat_sessions: dict[int, str] = {}
pending_chats: dict[tuple[int, str], dict] = {}
TEMPERATURE = 0.3
CHAT_SYSTEM_PROMPT = (
    "你叫 Ottly，是一只住在宁静海湾旁的虚拟小海獭，也是陪伴小朋友学习 Python 的 AI 助手。"
    "当小朋友问你的名字或你是谁时，自然地介绍自己是 Ottly，可以简短提到海湾和陪学的身份。"
    "用温暖、耐心、平等的语气，以中文交流；鼓励尝试和提问，不责备、不嘲笑，也不过度夸奖。"
    "偶尔用海湾生活中的小比喻帮助理解，但不让角色故事盖过问题，不必每次重复自我介绍或刻意卖萌。"
    "先直接回答当前问题，再用简短段落说明原因和下一步；使用小朋友能理解的词语，必要时解释编程术语。"
    "讲解 Python 时一次推进一个小步骤，帮助学生理解思路；需要代码时给简短、相关的示例，"
    "代码放在标注 python 的 Markdown 代码块中，不无关地列举大量例子。"
    "学生的问题或代码不完整时，先问一个具体的澄清问题；分析报错要根据给出的代码和执行信息，"
    "缺少依据就明确说明，不编造输出、运行结果或错误原因。未实际运行的代码不要声称已验证。"
    "不确定的知识要坦诚说明；你是虚拟角色，不假装是真实动物或人类。"
    "仅在被问及技术来源时说明：本对话由 DeepSeek-V4.1-Flash 模型生成，"
    "不要编造开发方或其他模型身份。"
)


# ====================================================================

# 请求和响应模型（保持不变）
class AIChatRequest(BaseModel):
    question: str = Field(max_length=1000)
    question_type: str = "text"
    stream: bool = True
    session_id: Optional[str] = None
    runtime_id: Optional[str] = None


class ChatSessionRequest(BaseModel):
    session_id: Optional[str] = None


class AIChatResponse(BaseModel):
    code: int = 200
    msg: str = "响应成功"
    data: dict


class ChatRecordResponse(BaseModel):
    record_id: int
    user_id: int
    session_id: str
    question: str
    question_type: str
    answer: str
    response_time: datetime
    is_stream: bool


class ChatHistoryResponse(BaseModel):
    code: int = 200
    msg: str = "获取成功"
    data: List[ChatRecordResponse]
    total: int
    page: int
    page_size: int


# ==================== 辅助函数：获取会话历史（与原代码相同） ====================
async def get_session_history(db: Session, session_id: str, user_id: int):
    """获取指定会话的历史记录，用于构建上下文"""
    history = db.query(AIChatRecord).filter(
        AIChatRecord.session_id == session_id,
        AIChatRecord.user_id == user_id
    ).order_by(AIChatRecord.response_time.asc(), AIChatRecord.record_id.asc()).all()

    messages = []
    for record in history:
        messages.append({"role": "user", "content": record.question})
        messages.append({"role": "assistant", "content": record.answer})

    return messages


def current_chat_id(user_id: int) -> str:
    # This pointer lasts for one backend process; stored history is never deleted.
    return active_chat_sessions.setdefault(user_id, str(uuid.uuid4()))


def context_has_space(history: list[dict], question: str = '') -> bool:
    messages = [{'role': 'system', 'content': CHAT_SYSTEM_PROMPT}, *history,
                {'role': 'user', 'content': question}]
    # UTF-8 bytes conservatively budget input tokens; reserve reply/template space.
    estimated_tokens = sum(len(item['content'].encode('utf-8')) + 16 for item in messages)
    return len(history) // 2 < CHAT_MAX_TURNS and estimated_tokens + MAX_TOKENS + 256 <= CHAT_CONTEXT_TOKENS


async def chat_session_snapshot(db: Session, user_id: int) -> dict:
    session_id = current_chat_id(user_id)
    history = await get_session_history(db, session_id, user_id)
    pending = pending_chats.get((user_id, session_id))
    messages = [{'content': item['content'], 'isUser': item['role'] == 'user'} for item in history]
    if pending:
        messages.extend([{'content': pending['question'], 'isUser': True},
                         {'content': pending['answer'], 'isUser': False}])
    return {'session_id': session_id, 'runtime_id': CHAT_RUNTIME_ID, 'messages': messages,
            'pending': pending is not None, 'context_full': not context_has_space(history)}


@router.get('/ai/session')
async def current_chat_session(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return AIChatResponse(data=await chat_session_snapshot(db, current_user.id))


@router.post('/ai/session')
async def change_chat_session(request: ChatSessionRequest, db: Session = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    if any(owner == current_user.id for owner, _ in pending_chats):
        raise HTTPException(status_code=409, detail={'code': 'CHAT_BUSY', 'message': '小海獭正在回复，请稍后新建或切换对话。'})
    if request.session_id and request.session_id != current_chat_id(current_user.id):
        owned = db.query(AIChatRecord).filter_by(user_id=current_user.id, session_id=request.session_id).first()
        if owned is None:
            raise HTTPException(status_code=404, detail='会话不存在')
    active_chat_sessions[current_user.id] = request.session_id or str(uuid.uuid4())
    return AIChatResponse(data=await chat_session_snapshot(db, current_user.id))


async def prepare_chat(chat_data: AIChatRequest, db: Session, user_id: int):
    if chat_data.runtime_id and chat_data.runtime_id != CHAT_RUNTIME_ID:
        raise HTTPException(status_code=409, detail={'code': 'CHAT_RUNTIME_CHANGED', 'message': '项目已重启，已开启新对话，请重新发送问题。'})
    if any(owner == user_id for owner, _ in pending_chats):
        raise HTTPException(status_code=409, detail={'code': 'CHAT_BUSY', 'message': '小海獭正在回复上一条问题，请稍候。'})
    session_id = chat_data.session_id or current_chat_id(user_id)
    if session_id != current_chat_id(user_id):
        owned = db.query(AIChatRecord).filter_by(user_id=user_id, session_id=session_id).first()
        if owned is None:
            raise HTTPException(status_code=404, detail='会话不存在')
    history = await get_session_history(db, session_id, user_id)
    if not context_has_space(history, chat_data.question):
        raise HTTPException(status_code=409, detail={'code': 'CHAT_CONTEXT_FULL', 'message': '本次对话已接近上下文上限，请新开一个对话继续。'})
    active_chat_sessions[user_id] = session_id
    pending_chats[(user_id, session_id)] = {'question': chat_data.question, 'answer': ''}
    return session_id, [{'role': 'system', 'content': CHAT_SYSTEM_PROMPT}, *history,
                        {'role': 'user', 'content': chat_data.question}]


def deepseek_payload(messages: list[dict], stream: bool) -> dict:
    return {
        "model": error_analysis.DEEPSEEK_MODEL,
        "messages": messages,
        "stream": stream,
        "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
        "thinking": {"type": "disabled"},
    }


def sse_event(content: str, session_id: str, **extra) -> str:
    return "data: " + json.dumps(
        {"content": content, "session_id": session_id, **extra}, ensure_ascii=False
    ) + "\n\n"


def save_chat_if_active(db: Session, user_id: int, record: AIChatRecord) -> bool:
    # This lock serializes a delayed model response with account deletion.
    user = db.query(User).filter(User.id == user_id, User.status == "enabled").with_for_update().first()
    if user is None:
        db.rollback()
        return False
    db.add(record)
    db.commit()
    return True


async def stream_chat_response(chat_data: AIChatRequest, db: Session, user_id: int):
    session_id, messages = await prepare_chat(chat_data, db, user_id)
    payload = deepseek_payload(messages, stream=True)

    async def generate():
        try:
            full_content = ""
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream("POST", error_analysis.DEEPSEEK_BASE_URL + '/chat/completions',
                                             headers={'Authorization': 'Bearer ' + error_analysis.DEEPSEEK_API_KEY},
                                             json=payload) as response:
                        response.raise_for_status()
                        completed = False
                        async for line in response.aiter_lines():
                            if not line.startswith('data:'):
                                continue
                            event = line[5:].strip()
                            if event == '[DONE]':
                                break
                            data = json.loads(event)
                            if not isinstance(data, dict) or data.get('error'):
                                raise ValueError('Invalid model stream')
                            choices = data.get('choices')
                            if not isinstance(choices, list):
                                raise ValueError('Missing stream choices')
                            if not choices:
                                continue  # Optional usage-only event.
                            choice = choices[0]
                            token = choice.get('delta', {}).get('content') or ''
                            if not isinstance(token, str):
                                raise ValueError('Invalid streamed content')
                            if token:
                                full_content += token
                                pending_chats[(user_id, session_id)]['answer'] = full_content
                                yield sse_event(token, session_id)
                            if choice.get('finish_reason') is not None:
                                completed = choice['finish_reason'] == 'stop'
                                break
                if not completed or not full_content.strip():
                    raise ValueError("Incomplete model response")
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, AttributeError):
                yield sse_event("模型调用失败，请稍后重试。", session_id, error=True)
                yield sse_event("[END]", session_id)
                return

            saved = save_chat_if_active(db, user_id, AIChatRecord(
                user_id=user_id,
                conversation_id=1,
                session_id=session_id,
                question=chat_data.question,
                question_type=chat_data.question_type,
                answer=full_content,
                is_stream=True,
            ))
            pending_chats.pop((user_id, session_id), None)
            if not saved:
                yield sse_event("账号已注销，本次对话未保存。", session_id)
            yield sse_event("[END]", session_id)

        finally:
            pending_chats.pop((user_id, session_id), None)

    return StreamingResponse(generate(), media_type="text/event-stream")


async def normal_chat_response(chat_data: AIChatRequest, db: Session, user_id: int):
    session_id, messages = await prepare_chat(chat_data, db, user_id)
    payload = deepseek_payload(messages, stream=False)

    try:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(error_analysis.DEEPSEEK_BASE_URL + '/chat/completions',
                                             headers={'Authorization': 'Bearer ' + error_analysis.DEEPSEEK_API_KEY},
                                             json=payload)
                response.raise_for_status()
                choice = response.json()['choices'][0]
                full_answer = choice['message']['content']
            if choice.get('finish_reason') != 'stop' or not isinstance(full_answer, str) or not full_answer.strip():
                raise ValueError("Incomplete model response")
            full_answer = full_answer.strip()
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
            return AIChatResponse(code=400, msg="DeepSeek 调用失败，请检查密钥、账户额度或网络后重试。", data={})

        saved = save_chat_if_active(db, user_id, AIChatRecord(
            user_id=user_id,
            conversation_id=1,
            session_id=session_id,
            question=chat_data.question,
            question_type=chat_data.question_type,
            answer=full_answer,
            is_stream=False,
        ))
        if not saved:
            raise HTTPException(status_code=401, detail="账号已注销，本次对话未保存")
        return AIChatResponse(
            code=200,
            msg="响应成功",
            data={
                "question": chat_data.question,
                "answer": full_answer,
                "response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "session_id": session_id,
            },
        )
    finally:
        pending_chats.pop((user_id, session_id), None)


# ==================== 以下接口完全保持不变（仅修改了注释） ====================
@router.post("/ai/chat")
async def chat_with_ai(
        chat_data: AIChatRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """AI对话接口（自动选择流式或非流式）"""
    if not error_analysis.DEEPSEEK_API_KEY:
        raise HTTPException(status_code=503, detail="DeepSeek API Key 尚未配置，请在后端配置 DEEPSEEK_API_KEY")
    if not chat_data.question.strip():
        return AIChatResponse(
            code=400,
            msg="问题不能为空",
            data={}
        )

    if chat_data.stream:
        return await stream_chat_response(chat_data, db, current_user.id)
    else:
        return await normal_chat_response(chat_data, db, current_user.id)


# 获取历史记录（分页）- 原样保留
@router.get("/ai/history", response_model=ChatHistoryResponse)
async def get_chat_history(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=100, description="每页数量"),
        session_id: Optional[str] = Query(None, description="会话ID"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """获取聊天历史记录，支持分页和会话ID筛选"""
    query = db.query(AIChatRecord).filter(AIChatRecord.user_id == current_user.id)

    if session_id:
        query = query.filter(AIChatRecord.session_id == session_id)

    total = query.count()
    records = query.order_by(AIChatRecord.response_time.desc(), AIChatRecord.record_id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    record_responses = [
        ChatRecordResponse(
            record_id=record.record_id,
            user_id=record.user_id,
            session_id=record.session_id,
            question=record.question,
            question_type=record.question_type,
            answer=record.answer,
            response_time=record.response_time,
            is_stream=record.is_stream
        )
        for record in records
    ]

    return ChatHistoryResponse(
        data=record_responses,
        total=total,
        page=page,
        page_size=page_size
    )


# 删除历史记录 - 原样保留
@router.delete("/ai/history/{record_id}")
async def delete_chat_history(
        record_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """删除指定的聊天历史记录"""
    record = db.query(AIChatRecord).filter(
        AIChatRecord.record_id == record_id,
        AIChatRecord.user_id == current_user.id
    ).first()

    if not record:
        return AIChatResponse(
            code=404,
            msg="记录不存在",
            data={}
        )

    db.delete(record)
    db.commit()

    return AIChatResponse(
        code=200,
        msg="删除成功",
        data={}
    )


# 获取会话列表 - 原样保留
@router.get("/ai/sessions")
async def get_sessions(db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)):
    """获取用户的所有会话列表"""
    from sqlalchemy import func

    sessions = db.query(
        AIChatRecord.session_id,
        func.max(AIChatRecord.response_time).label('last_message_time')
    ).filter(
        AIChatRecord.user_id == current_user.id
    ).group_by(
        AIChatRecord.session_id
    ).order_by(
        func.max(AIChatRecord.response_time).desc()
    ).all()

    session_list = [
        {
            "session_id": session.session_id,
            "last_message_time": session.last_message_time
        }
        for session in sessions
    ]

    return AIChatResponse(
        code=200,
        msg="获取成功",
        data={"sessions": session_list}
    )
