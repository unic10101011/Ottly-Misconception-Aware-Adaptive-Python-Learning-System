# ==================== 完整的 ai.py ====================
from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import AIChatRecord
from pydantic import BaseModel
import json
import asyncio
import uuid
from datetime import datetime
from typing import List, Optional
import httpx  # 【修改】新增：用于异步HTTP请求，替换原来的 openai 库

router = APIRouter()

# ==================== 【修改】本地大模型配置（替换原来的蓝心大模型配置） ====================
LOCAL_LLM_URL = "http://172.23.46.241:8000/v1/chat/completions"
MAX_TOKENS = 300  # 可根据需要调整
TEMPERATURE = 0.7


# ====================================================================

# 请求和响应模型（保持不变）
class AIChatRequest(BaseModel):
    question: str
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
async def get_session_history(db: Session, session_id: str):
    """获取指定会话的历史记录，用于构建上下文"""
    history = db.query(AIChatRecord).filter(
        AIChatRecord.session_id == session_id
    ).order_by(AIChatRecord.response_time.asc()).all()

    messages = []
    for record in history:
        messages.append({"role": "user", "content": record.question})
        messages.append({"role": "assistant", "content": record.answer})

    return messages


# ==================== 【修改】流式响应 - 改用本地模型 ====================
async def stream_chat_response(chat_data: AIChatRequest, db: Session):
    # 生成或使用现有的会话ID
    session_id = chat_data.session_id or str(uuid.uuid4())

    # 获取历史记录作为上下文
    history_messages = await get_session_history(db, session_id)

    # 构建完整的消息列表
    messages = history_messages + [{"role": "user", "content": chat_data.question}]

    # 【修改】构造本地模型的请求体
    payload = {
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE
    }

    full_content = ""

    async def generate():
        nonlocal full_content
        # 【修改】使用 httpx 异步客户端发送流式请求
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", LOCAL_LLM_URL, json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    yield f"data: {{\"content\": \"调用本地模型失败: {response.status_code}\", \"session_id\": \"{session_id}\"}}\n\n"
                    yield f"data: {{\"content\": \"[END]\"}}\n\n"
                    return

                # 逐行读取 SSE 流
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # 去掉 "data: " 前缀
                        if data_str.strip():
                            try:
                                data = json.loads(data_str)
                                # 【修改】本地模型返回格式为 {"token": "..."}，需转换为前端期望的 {"content": "..."}
                                if "token" in data:
                                    token = data["token"]
                                    full_content += token
                                    yield f"data: {{\"content\": \"{token}\", \"session_id\": \"{session_id}\"}}\n\n"
                                if data.get("done"):
                                    break
                            except json.JSONDecodeError:
                                continue

        # 发送结束标记（与原逻辑一致）
        yield f"data: {{\"content\": \"[END]\", \"session_id\": \"{session_id}\"}}\n\n"

        # 保存对话记录到数据库（与原逻辑一致）
        chat_record = AIChatRecord(
            user_id=1,  # 默认用户ID，可根据实际认证修改
            conversation_id=1,  # 原代码中使用的默认值
            session_id=session_id,
            question=chat_data.question,
            question_type=chat_data.question_type,
            answer=full_content,
            is_stream=True
        )
        db.add(chat_record)
        db.commit()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


# ==================== 【修改】非流式响应 - 改用本地模型 ====================
async def normal_chat_response(chat_data: AIChatRequest, db: Session):
    # 生成或使用现有的会话ID
    session_id = chat_data.session_id or str(uuid.uuid4())

    # 获取历史记录作为上下文
    history_messages = await get_session_history(db, session_id)

    # 构建完整的消息列表
    messages = history_messages + [{"role": "user", "content": chat_data.question}]

    payload = {
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE
    }

    try:
        # 【修改】使用 httpx 发送请求
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(LOCAL_LLM_URL, json=payload)
            if response.status_code != 200:
                raise Exception(f"本地模型返回错误: {response.status_code}")

            # 【修改】本地模型 API 返回的是流式 SSE，这里解析流式并拼接完整回答
            full_answer = ""
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip():
                        try:
                            data = json.loads(data_str)
                            if "token" in data:
                                full_answer += data["token"]
                            if data.get("done"):
                                break
                        except:
                            pass
            if not full_answer:
                full_answer = "抱歉，模型没有返回有效回答。"

        # 保存记录（与原逻辑一致）
        chat_record = AIChatRecord(
            user_id=1,
            conversation_id=1,
            session_id=session_id,
            question=chat_data.question,
            question_type=chat_data.question_type,
            answer=full_answer,
            is_stream=False
        )
        db.add(chat_record)
        db.commit()

        return AIChatResponse(
            code=200,
            msg="响应成功",
            data={
                "question": chat_data.question,
                "answer": full_answer,
                "response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "session_id": session_id
            }
        )

    except Exception as e:
        return AIChatResponse(
            code=400,
            msg=f"本地大模型调用失败: {str(e)}",
            data={}
        )


# ==================== 以下接口完全保持不变（仅修改了注释） ====================
@router.post("/ai/chat")
async def chat_with_ai(
        chat_data: AIChatRequest,
        db: Session = Depends(get_db)
):
    """AI对话接口（自动选择流式或非流式）"""
    if not chat_data.question:
        return AIChatResponse(
            code=400,
            msg="问题不能为空",
            data={}
        )

    if chat_data.stream:
        return await stream_chat_response(chat_data, db)
    else:
        return await normal_chat_response(chat_data, db)


# 获取历史记录（分页）- 原样保留
@router.get("/ai/history", response_model=ChatHistoryResponse)
async def get_chat_history(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=100, description="每页数量"),
        session_id: Optional[str] = Query(None, description="会话ID"),
        db: Session = Depends(get_db)
):
    """获取聊天历史记录，支持分页和会话ID筛选"""
    query = db.query(AIChatRecord).filter(AIChatRecord.user_id == 1)

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
        db: Session = Depends(get_db)
):
    """删除指定的聊天历史记录"""
    record = db.query(AIChatRecord).filter(
        AIChatRecord.record_id == record_id,
        AIChatRecord.user_id == 1
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
async def get_sessions(db: Session = Depends(get_db)):
    """获取用户的所有会话列表"""
    from sqlalchemy import func

    sessions = db.query(
        AIChatRecord.session_id,
        func.max(AIChatRecord.response_time).label('last_message_time')
    ).filter(
        AIChatRecord.user_id == 1
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