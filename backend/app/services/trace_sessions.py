"""Short-lived, bounded replay sessions; never persisted as judged submissions."""
import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
import json
import secrets
import time

from fastapi import HTTPException

TTL = 15 * 60
MAX_SESSIONS = 32
MAX_BYTES = 16 * 1024 * 1024
SESSIONS = OrderedDict()


@dataclass
class TraceSession:
    user_id: int
    data: dict
    expires_at: float
    size: int
    answers: dict = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def trim():
    now = time.monotonic()
    for key in list(SESSIONS):
        if SESSIONS[key].expires_at <= now:
            del SESSIONS[key]
    while len(SESSIONS) > MAX_SESSIONS or sum(s.size for s in SESSIONS.values()) > MAX_BYTES:
        SESSIONS.popitem(last=False)


def remember_trace(user_id, data):
    token = secrets.token_urlsafe(24)
    size = len(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    SESSIONS[token] = TraceSession(user_id, data, time.monotonic() + TTL, size)
    trim()
    return token


def owned_trace(token, user_id):
    session = SESSIONS.get(token)
    if session is None:
        raise HTTPException(410, '回放会话已过期或服务已重启，请重新打开回放。')
    if session.user_id != user_id:
        raise HTTPException(404, '找不到当前账号的回放。')
    if session.expires_at <= time.monotonic():
        del SESSIONS[token]
        raise HTTPException(410, '回放会话已过期，请重新打开回放。')
    SESSIONS.move_to_end(token)
    return session


def cache_answer(session, index, result):
    session.answers[index] = result
    session.size += len(json.dumps(result, ensure_ascii=False).encode('utf-8'))
    trim()
