import json
import time

import httpx
import pytest

from test_learning_history import client, account
from test_guide_questions import cloud


def test_explanation_uses_owned_server_trace_and_caches(client, monkeypatch):
    from app.services import trace_sessions
    seen = []

    def handler(request):
        body = json.loads(request.content)
        assert body['thinking'] == {'type': 'disabled'} and body['max_tokens'] <= 512
        payload = json.loads(body['messages'][-1]['content'])
        assert payload['code'] == "name = input()\nprint(name)"
        assert payload['current']['variables']['name'] == "'Ottly'"
        assert 'reference_solution' not in payload and 'tests' not in payload
        seen.append(payload)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': 'name 保存了输入的文字。你觉得换个名字后会输出什么？'}}]})

    cloud(monkeypatch, handler)
    headers = account(client, 'trace_ask_owner', '13800000501')
    other = account(client, 'trace_ask_other', '13800000502')
    # The normal unlock check remains in place; only the isolated fixture supplies prior progress.
    from app.api import execution_trace
    monkeypatch.setattr(execution_trace, 'passed_problem_ids', lambda db, user: {'level1'})
    replay = client.post('/api/v1/code/execution-trace', headers=headers, json={
        'problem_id': 'greeting-v1', 'code': "name = input()\nprint(name)", 'stdin': 'Ottly\n',
    }).json()['data']
    assert seen == [], 'recording a trace must never request AI'
    trace_id = replay['trace_id']
    path = f'/api/v1/code/execution-trace/{trace_id}/explanation'
    assert client.post(path, json={'step_index': 1}).status_code == 401
    assert client.post(path, headers=other, json={'step_index': 1}).status_code == 404
    assert client.post(path, headers=headers, json={'step_index': 999}).status_code == 422
    assert client.post(path, headers=headers, json={'step_index': 1, 'code': 'fake'}).status_code == 422
    first = client.post(path, headers=headers, json={'step_index': 1})
    assert first.status_code == 200, first.text
    assert first.json()['data']['cached'] is False and first.json()['data']['answer']
    second = client.post(path, headers=headers, json={'step_index': 1})
    assert second.json()['data']['cached'] is True and len(seen) == 1
    assert client.get('/api/v1/code/submissions', headers=headers).json()['data']['total'] == 0
    trace_sessions.SESSIONS[trace_id].expires_at = time.monotonic() - 1
    assert client.post(path, headers=headers, json={'step_index': 1}).status_code == 410


@pytest.mark.parametrize('failure,status', [('timeout', 504), ('empty', 502), (429, 503)])
def test_explanation_failure_is_retryable_and_never_leaks(client, monkeypatch, failure, status):
    def handler(request):
        if failure == 'timeout':
            raise httpx.ReadTimeout('SECRET_PROVIDER_ERROR')
        if isinstance(failure, int):
            return httpx.Response(failure, text='SECRET_PROVIDER_ERROR')
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': ''}}]})
    cloud(monkeypatch, handler)
    headers = account(client, 'trace_ask_failure', '13800000503')
    replay = client.post('/api/v1/code/execution-trace', headers=headers, json={'problem_id': 'level1', 'code': 'print(1)'}).json()['data']
    response = client.post(f"/api/v1/code/execution-trace/{replay['trace_id']}/explanation", headers=headers, json={'step_index': 0})
    assert response.status_code == status, response.text
    assert 'SECRET' not in response.text
