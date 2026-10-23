# ==================== 完整的 ai.py ====================
from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import AIChatRecord
from pydantic import BaseModel, Field
import json
import asyncio
import uuid
from datetime import datetime
from typing import List, Optional
import os
from app.core.auth import get_current_user
from app.models.user import User
import httpx  # 【修改】新增：用于异步HTTP请求，替换原来的 openai 库

router = APIRouter()

# ==================== 【修改】本地大模型配置（替换原来的蓝心大模型配置） ====================
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b-instruct-q4_K_M")
MAX_TOKENS = 450
TEMPERATURE = 0.3
CHAT_SYSTEM_PROMPT = (
    "你是面向 Python 初学者的中文编程辅导助手。先直接回答学生当前问题，"
    "用简短段落解释原因和下一步。只有确实需要时才给一个简短代码示例，"
    "代码放在标注 python 的 Markdown 代码块中。不要无关地列举大量例子；"
    "未实际运行的代码不要声称已验证输出。学生问题不明确时先问一个澄清问题。"
)


# ====================================================================

# 请求和响应模型（保持不变）
class AIChatRequest(BaseModel):
    question: str = Field(max_length=1000)
    question_type: str = "text"
    stream: bool = True
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
    ).order_by(AIChatRecord.response_time.asc()).all()

    messages = []
    for record in history:
        messages.append({"role": "user", "content": record.question})
        messages.append({"role": "assistant", "content": record.answer})

    return messages


def ollama_payload(messages: list[dict], stream: bool) -> dict:
    return {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": stream,
        "options": {"num_predict": MAX_TOKENS, "temperature": TEMPERATURE},
    }


def sse_event(content: str, session_id: str) -> str:
    return "data: " + json.dumps(
        {"content": content, "session_id": session_id}, ensure_ascii=False
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
    session_id = chat_data.session_id or str(uuid.uuid4())
    history_messages = await get_session_history(db, session_id, user_id)
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + history_messages[-8:] + [{"role": "user", "content": chat_data.question}]
    payload = ollama_payload(messages, stream=True)

    async def generate():
        full_content = ""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", LOCAL_LLM_URL, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            full_content += token
                            yield sse_event(token, session_id)
                        if data.get("done"):
                            break
            if not full_content:
                raise ValueError("Empty model response")
        except (httpx.HTTPError, ValueError):
            yield sse_event("模型调用失败，请稍后重试。", session_id)
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
        if not saved:
            yield sse_event("账号已注销，本次对话未保存。", session_id)
        yield sse_event("[END]", session_id)

    return StreamingResponse(generate(), media_type="text/event-stream")


async def normal_chat_response(chat_data: AIChatRequest, db: Session, user_id: int):
    session_id = chat_data.session_id or str(uuid.uuid4())
    history_messages = await get_session_history(db, session_id, user_id)
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + history_messages[-8:] + [{"role": "user", "content": chat_data.question}]
    payload = ollama_payload(messages, stream=False)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(LOCAL_LLM_URL, json=payload)
            response.raise_for_status()
            full_answer = response.json().get("message", {}).get("content", "").strip()
        if not full_answer:
            raise ValueError("Empty model response")
    except (httpx.HTTPError, ValueError):
        return AIChatResponse(code=400, msg="模型调用失败，请检查 Ollama 服务和模型。", data={})

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


# ==================== 以下接口完全保持不变（仅修改了注释） ====================
@router.post("/ai/chat")
async def chat_with_ai(
        chat_data: AIChatRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """AI对话接口（自动选择流式或非流式）"""
    if not LOCAL_LLM_URL:
        raise HTTPException(status_code=503, detail="AI 模型地址尚未配置")
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
    records = query.order_by(AIChatRecord.response_time.desc()).offset(
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
