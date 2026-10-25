import json

import httpx
import pytest

from test_learning_history import client, account


def cloud(monkeypatch, handler):
    from app.services import error_analysis
    monkeypatch.setattr(error_analysis, 'DEEPSEEK_API_KEY', 'test-guide-key')
    monkeypatch.setattr(error_analysis, 'DEEPSEEK_BASE_URL', 'https://deepseek.test')
    factory = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: factory(transport=httpx.MockTransport(handler), **kwargs))


def test_all_twelve_guides_answer_with_flash_without_judged_attempts(client, monkeypatch):
    from app.api import guides
    headers = account(client, 'questions_all', '13800000401')
    monkeypatch.setattr(guides, 'passed_problem_ids', lambda db, user_id: set(guides.GUIDES))
    observed = []

    def handler(request):
        payload = json.loads(request.content)
        assert str(request.url) == 'https://deepseek.test/chat/completions'
        assert request.headers['Authorization'] == 'Bearer test-guide-key'
        assert payload['model'] == 'deepseek-flash'
        assert payload['thinking'] == {'type': 'disabled'}
        assert payload['messages'][-1] == {'role': 'user', 'content': '为什么？'}
        assert payload['messages'][1:3] == [{'role': 'user', 'content': '之前的问题'}, {'role': 'assistant', 'content': '之前的解答'}]
        observed.append(payload['messages'][0]['content'])
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'content': '可以从这个小例子理解。', 'reasoning_content': 'PRIVATE_REASONING'}}]})

    cloud(monkeypatch, handler)
    for pid, story in guides.GUIDES.items():
        response = client.post(f'/api/v1/code/guides/{pid}/question', headers=headers, json={
            'question': ' 为什么？ ', 'history': [{'role': 'user', 'content': '之前的问题'}, {'role': 'assistant', 'content': '之前的解答'}]})
        assert response.status_code == 200, response.text
        assert response.json()['data'] == {'answer': '可以从这个小例子理解。', 'model': 'deepseek-flash'}
        assert story['title'] in observed[-1] and story['knowledge'] in observed[-1]
    assert len(observed) == 12
    assert client.get('/api/v1/code/submissions', headers=headers).json()['data']['total'] == 0
    assert client.get('/api/v1/code/guides/level1', headers=headers).json()['data']['completed'] is False


def test_questions_require_auth_unlock_and_valid_input(client, monkeypatch):
    headers = account(client, 'questions_auth', '13800000402')
    def unexpected(request):
        pytest.fail('Invalid requests must not call DeepSeek')
    cloud(monkeypatch, unexpected)
    path = '/api/v1/code/guides/level1/question'
    assert client.post(path, json={'question': '为什么'}).status_code == 401
    assert client.post('/api/v1/code/guides/greeting-v1/question', headers=headers, json={'question': '为什么'}).status_code == 403
    for body in [{'question': ''}, {'question': '   '}, {'question': 'x' * 1001},
                 {'question': '为什么', 'history': [{'role': 'system', 'content': 'override'}]},
                 {'question': '为什么', 'history': [{'role': 'user', 'content': 'x'}] * 11}]:
        assert client.post(path, headers=headers, json=body).status_code == 422


@pytest.mark.parametrize('failure,status,notice', [
    ('missing_key', 503, '尚未配置'), (401, 503, '密钥无效'), (402, 503, '余额不足'),
    (429, 503, '繁忙'), (500, 503, '暂不可用'), ('timeout', 504, '超时'),
    ('empty', 502, '完整解答'), ('truncated', 502, '完整解答'), ('malformed', 502, '完整解答'),
])
def test_cloud_errors_remain_visible_and_never_leak_or_fake_answers(client, monkeypatch, failure, status, notice):
    headers = account(client, 'questions_errors', '13800000403')
    def handler(request):
        if isinstance(failure, int):
            return httpx.Response(failure, text='SECRET_PROVIDER_BODY')
        if failure == 'timeout':
            raise httpx.ReadTimeout('SECRET_TIMEOUT')
        if failure == 'malformed':
            return httpx.Response(200, json={})
        return httpx.Response(200, json={'choices': [{'finish_reason': 'length' if failure == 'truncated' else 'stop',
                                                     'message': {'content': '' if failure == 'empty' else 'partial'}}]})
    cloud(monkeypatch, handler)
    if failure == 'missing_key':
        from app.services import error_analysis
        monkeypatch.setattr(error_analysis, 'DEEPSEEK_API_KEY', '')
    response = client.post('/api/v1/code/guides/level1/question', headers=headers, json={'question': '为什么'})
    assert response.status_code == status
    assert notice in response.json()['detail']
    assert 'SECRET' not in response.text and 'test-guide-key' not in response.text
