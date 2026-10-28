"""Bound analysis/recommendation work in the single-process demo backend."""
from contextlib import contextmanager
import threading

from fastapi import HTTPException

_RUNNING = set()
_LOCK = threading.Lock()
MAX_ACTIVE = 4
MAX_PER_USER = 2


@contextmanager
def ai_operation(user_id, kind, item_id):
    key = (user_id, kind, item_id)
    with _LOCK:
        if key in _RUNNING:
            raise HTTPException(409, '本次请求正在处理中，请等待完成后再查看。')
        if len(_RUNNING) >= MAX_ACTIVE or sum(item[0] == user_id for item in _RUNNING) >= MAX_PER_USER:
            raise HTTPException(429, 'AI 请求较多，请稍后重试。')
        _RUNNING.add(key)
    try:
        yield
    finally:
        with _LOCK:
            _RUNNING.discard(key)
