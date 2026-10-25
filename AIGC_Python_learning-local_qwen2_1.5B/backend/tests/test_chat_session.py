import asyncio
import json

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from test_submission import client, login


@pytest.fixture(autouse=True)
def chat_runtime(monkeypatch):
    from app.api import ai
    monkeypatch.setattr(ai, 'active_chat_sessions', {})
    monkeypatch.setattr(ai, 'pending_chats', {})
    monkeypatch.setattr(ai, 'CHAT_RUNTIME_ID', 'boot-one')
    monkeypatch.setattr(ai.error_analysis, 'DEEPSEEK_API_KEY', 'test-chat-key')
    monkeypatch.setattr(ai.error_analysis, 'DEEPSEEK_BASE_URL', 'https://deepseek.test')
    requests = []

    def reply(request):
        payload = json.loads(request.content)
        assert str(request.url) == 'https://deepseek.test/chat/completions'
        assert request.headers['Authorization'] == 'Bearer test-chat-key'
        assert payload['model'] == 'deepseek-flash'
        assert payload['thinking'] == {'type': 'disabled'}
        requests.append(payload)
        if payload['stream']:
            return httpx.Response(200, text='\n\n'.join('data: ' + json.dumps(item) for item in [
                {'choices': [{'delta': {'content': '保留', 'reasoning_content': 'PRIVATE_REASONING'}, 'finish_reason': None}]},
                {'choices': [{'delta': {'content': '上下文。'}, 'finish_reason': 'stop'}]},
            ]) + '\n')
        return httpx.Response(200, json={'choices': [{'message': {'content': '保留上下文。', 'reasoning_content': 'PRIVATE_REASONING'}, 'finish_reason': 'stop'}]})

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(reply)
    monkeypatch.setattr(ai.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=transport, **kwargs))
    return requests


def test_returning_restores_current_session_and_model_keeps_more_than_four_turns(client, chat_runtime):
    headers = login(client)
    first = client.get('/api/v1/ai/session', headers=headers).json()['data']
    for index in range(6):
        response = client.post('/api/v1/ai/chat', headers=headers, json={
            'question': f'问题{index}', 'stream': False, 'runtime_id': first['runtime_id'],
        })
        assert response.status_code == 200
        assert response.json()['data']['session_id'] == first['session_id']
    restored = client.get('/api/v1/ai/session', headers=headers).json()['data']
    assert restored['session_id'] == first['session_id']
    assert [item['content'] for item in restored['messages'][::2]] == [f'问题{i}' for i in range(6)]
    assert len(chat_runtime[-1]['messages']) == 12
    assert chat_runtime[-1]['messages'][1]['content'] == '问题0'
    assert 'options' not in chat_runtime[-1]
    assert chat_runtime[-1]['max_tokens'] == 450
    assert restored['pending'] is False


def test_restart_opens_new_session_without_deleting_history_or_reusing_old_runtime(client, monkeypatch, chat_runtime):
    from app.api import ai
    headers = login(client)
    first = client.post('/api/v1/ai/chat', headers=headers,
                        json={'question': '旧问题', 'stream': False}).json()['data']
    ai.active_chat_sessions.clear()
    monkeypatch.setattr(ai, 'CHAT_RUNTIME_ID', 'boot-two')
    fresh = client.get('/api/v1/ai/session', headers=headers).json()['data']
    assert fresh['session_id'] != first['session_id']
    assert fresh['messages'] == []
    assert client.get('/api/v1/ai/history', headers=headers).json()['total'] == 1
    rejected = client.post('/api/v1/ai/chat', headers=headers, json={
        'question': '旧页面的问题', 'session_id': first['session_id'], 'runtime_id': 'boot-one',
    })
    assert rejected.status_code == 409
    assert rejected.json()['detail']['code'] == 'CHAT_RUNTIME_CHANGED'
    assert len(chat_runtime) == 1


def test_new_session_and_old_session_selection_are_user_owned(client):
    owner = login(client)
    assert client.get('/api/v1/ai/session').status_code == 401
    old = client.post('/api/v1/ai/chat', headers=owner,
                      json={'question': '保留旧记录', 'stream': False}).json()['data']['session_id']
    fresh = client.post('/api/v1/ai/session', headers=owner, json={}).json()['data']
    assert fresh['session_id'] != old and fresh['messages'] == []
    selected = client.post('/api/v1/ai/session', headers=owner, json={'session_id': old}).json()['data']
    assert selected['messages'][0]['content'] == '保留旧记录'
    account = {'username': 'other_chat_user', 'password': 'TestPass1234!', 'phone': '13800000072'}
    client.post('/api/v1/auth/register', json=account)
    token = client.post('/api/v1/auth/login', json=account).json()['data']['access_token']
    other = {'Authorization': 'Bearer ' + token}
    assert client.get('/api/v1/ai/session', headers=other).json()['data']['messages'] == []
    assert client.post('/api/v1/ai/session', headers=other, json={'session_id': old}).status_code == 404
    assert client.post('/api/v1/ai/chat', headers=other,
                       json={'question': '越权续聊', 'session_id': old}).status_code == 404


@pytest.mark.parametrize('stream', [True, False])
def test_full_context_rejects_more_messages_before_calling_model_and_new_chat_recovers(client, monkeypatch, chat_runtime, stream):
    from app.api import ai
    monkeypatch.setattr(ai, 'CHAT_MAX_TURNS', 1)
    headers = login(client)
    client.post('/api/v1/ai/chat', headers=headers, json={'question': '第一轮', 'stream': False})
    snapshot = client.get('/api/v1/ai/session', headers=headers).json()['data']
    assert snapshot['context_full'] is True
    response = client.post('/api/v1/ai/chat', headers=headers, json={'question': '不要截断', 'stream': stream})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'CHAT_CONTEXT_FULL'
    assert len(chat_runtime) == 1
    assert client.get('/api/v1/ai/history', headers=headers).json()['total'] == 1
    fresh = client.post('/api/v1/ai/session', headers=headers, json={}).json()['data']
    assert fresh['context_full'] is False
    assert client.post('/api/v1/ai/chat', headers=headers,
                       json={'question': '新会话', 'stream': stream}).status_code == 200


def test_context_budget_also_protects_long_unicode_inputs(client, monkeypatch, chat_runtime):
    from app.api import ai
    monkeypatch.setattr(ai, 'CHAT_CONTEXT_TOKENS', 1800)
    headers = login(client)
    response = client.post('/api/v1/ai/chat', headers=headers, json={'question': '中' * 600})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'CHAT_CONTEXT_FULL'
    assert chat_runtime == []


def test_in_progress_stream_can_be_restored_and_blocks_switching_until_saved(tmp_path):
    from app.api import ai
    from app.core.database import Base
    from app.models.user import User
    from fastapi import HTTPException

    async def scenario():
        engine = create_engine(f'sqlite:///{tmp_path / "pending.sqlite"}')
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            user = User(username='pending_user', password='unused-hash', phone='13800000073')
            db.add(user)
            db.commit()
            response = await ai.stream_chat_response(ai.AIChatRequest(question='正在回复的问题'), db, user.id)
            before = await ai.chat_session_snapshot(db, user.id)
            assert before['pending'] is True
            assert before['messages'] == [{'content': '正在回复的问题', 'isUser': True}, {'content': '', 'isUser': False}]
            with pytest.raises(HTTPException) as busy:
                await ai.change_chat_session(ai.ChatSessionRequest(), db, user)
            assert busy.value.status_code == 409
            iterator = response.body_iterator
            await anext(iterator)
            during = await ai.chat_session_snapshot(db, user.id)
            assert during['messages'][-1]['content'] == '保留'
            async for _ in iterator:
                pass
            after = await ai.chat_session_snapshot(db, user.id)
            assert after['pending'] is False
            assert len(after['messages']) == 2
            assert after['messages'][-1]['content'] == '保留上下文。'
        engine.dispose()

    asyncio.run(scenario())


def test_cancelled_stream_releases_pending_slot(tmp_path):
    from app.api import ai
    from app.core.database import Base
    from app.models.user import User

    async def scenario():
        engine = create_engine(f'sqlite:///{tmp_path / "cancel.sqlite"}')
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            user = User(username='cancel_user', password='unused-hash', phone='13800000074')
            db.add(user)
            db.commit()
            response = await ai.stream_chat_response(ai.AIChatRequest(question='取消测试'), db, user.id)
            await anext(response.body_iterator)
            await response.body_iterator.aclose()
            assert not ai.pending_chats
        engine.dispose()

    asyncio.run(scenario())
