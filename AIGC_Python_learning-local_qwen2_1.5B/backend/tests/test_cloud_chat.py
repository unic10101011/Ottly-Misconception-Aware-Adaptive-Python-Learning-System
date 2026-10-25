"""Cloud chat preserves SSE/history behavior and never publishes reasoning."""
import json

import httpx
import pytest

from test_submission import client, login


@pytest.mark.parametrize('stream', [False, True])
def test_chat_requires_shared_cloud_credentials(client, monkeypatch, stream):
    from app.services import error_analysis
    monkeypatch.setattr(error_analysis, 'DEEPSEEK_API_KEY', '')
    response = client.post('/api/v1/ai/chat', headers=login(client),
                           json={'question': '你好', 'stream': stream})
    assert response.status_code == 503
    assert 'DEEPSEEK_API_KEY' in response.json()['detail']


@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('finish', ['stop', 'length', 'reasoning_only'])
def test_chat_saves_only_complete_public_answers(client, monkeypatch, stream, finish):
    from app.api import ai
    from app.services import error_analysis
    monkeypatch.setattr(error_analysis, 'DEEPSEEK_API_KEY', 'test-chat-key')
    monkeypatch.setattr(error_analysis, 'DEEPSEEK_BASE_URL', 'https://deepseek.test')
    observed = []

    def reply(request):
        payload = json.loads(request.content)
        observed.append(payload)
        assert str(request.url) == 'https://deepseek.test/chat/completions'
        assert request.headers['Authorization'] == 'Bearer test-chat-key'
        assert payload['model'] == 'deepseek-flash'
        assert payload['thinking'] == {'type': 'disabled'}
        assert 'options' not in payload
        content = '' if finish == 'reasoning_only' else 'PUBLIC_REPLY'
        reason = 'stop' if finish == 'reasoning_only' else finish
        if stream:
            chunks = [
                {'choices': [{'delta': {'reasoning_content': 'PRIVATE_REASONING'}, 'finish_reason': None}]},
                {'choices': [{'delta': {'content': content}, 'finish_reason': reason}]},
            ]
            return httpx.Response(200, text=': keep-alive\n\n' + '\n\n'.join(
                'data: ' + json.dumps(chunk) for chunk in chunks) + '\n\ndata: [DONE]\n\n')
        return httpx.Response(200, json={'choices': [{'finish_reason': reason, 'message': {
            'content': content, 'reasoning_content': 'PRIVATE_REASONING',
        }}]})

    factory = httpx.AsyncClient
    monkeypatch.setattr(ai.httpx, 'AsyncClient', lambda **kwargs: factory(
        transport=httpx.MockTransport(reply), **kwargs))
    headers = login(client)
    response = client.post('/api/v1/ai/chat', headers=headers,
                           json={'question': '解释一个循环', 'stream': stream})
    assert response.status_code == 200
    assert 'PRIVATE_REASONING' not in response.text
    history = client.get('/api/v1/ai/history', headers=headers).json()
    assert history['total'] == (1 if finish == 'stop' else 0)
    if finish == 'stop':
        assert 'PUBLIC_REPLY' in response.text
    else:
        assert '调用失败' in response.text
    assert not ai.pending_chats
    assert len(observed) == 1
