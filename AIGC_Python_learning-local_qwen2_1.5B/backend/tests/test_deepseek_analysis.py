"""Cloud diagnosis uses the shared evidence pipeline; chat stays on Ollama."""
import json
from pathlib import Path

import httpx
import pytest

from test_submission import client, login, submit_and_analyze


@pytest.fixture
def deepseek(monkeypatch):
    from app.services import error_analysis as service
    monkeypatch.setattr(service, 'ANALYSIS_PROVIDER', 'deepseek')
    monkeypatch.setattr(service, 'DEEPSEEK_API_KEY', 'test-only-cloud-key')
    monkeypatch.setattr(service, 'DEEPSEEK_BASE_URL', 'https://deepseek.test/v1')
    monkeypatch.setattr(service, 'DEEPSEEK_MODEL', 'deepseek-flash')
    # A cloud diagnosis must work without an Ollama endpoint.
    monkeypatch.setattr(service, 'LOCAL_LLM_URL', '')
    return service


def install_cloud(monkeypatch, handler):
    factory = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient',
                        lambda **kwargs: factory(transport=httpx.MockTransport(handler), **kwargs))


def completion(content, **message):
    return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
        'role': 'assistant', 'content': json.dumps(content, ensure_ascii=False),
        'reasoning_content': 'PRIVATE_REASONING_NOT_FOR_STUDENTS', **message,
    }}]})


def cloud_reply(request, observed):
    from app.services.problem_catalog import KNOWLEDGE, PROBLEMS
    payload = json.loads(request.content)
    assert str(request.url) == 'https://deepseek.test/v1/chat/completions'
    assert request.headers['Authorization'] == 'Bearer test-only-cloud-key'
    assert payload['model'] == 'deepseek-flash'
    assert payload['response_format'] == {'type': 'json_object'}
    assert payload['thinking'] == {'type': 'enabled'}
    assert payload['max_tokens'] >= 4096
    assert payload['stream'] is False
    assert 'format' not in payload and 'options' not in payload
    facts = json.JSONDecoder().raw_decode(payload['messages'][1]['content'])[0]
    observed.append(facts)
    if 'candidate' in facts:
        return completion({'tag_supported': True, 'issues': []})
    if 'public_cases' in facts:
        lesson = PROBLEMS[facts['problem']['problem_id']]
        return completion({
            'hint': '先对照题目要求，检查代码是否处理了不同输入。',
            'knowledge_points': [KNOWLEDGE[lesson.knowledge_ids[0]].name],
            'question': None,
        })
    name_error = any(error['type'] == 'NameError' for case in facts['failed_cases'] for error in case['errors'])
    lesson = PROBLEMS.get(facts['problem']['problem_id'])
    knowledge_id = lesson.knowledge_ids[0] if lesson else 'K02' if name_error else 'K01'
    return completion({
        'code_observation': '核对本次代码及公开执行结果。',
        'misconception_tag': 'other',
        'suspected_cause': ('疑似引用了尚未定义的名字。' if name_error else
                            '疑似当前操作或数据不符合要求，请结合本次执行证据核对。'),
        'evidence': [{**facts['allowed_evidence'][0], 'explanation': '这是本次实际运行产生的公开结果。'}],
        'knowledge_points': [KNOWLEDGE[knowledge_id].name],
    })


def test_cloud_diagnosis_and_review_cover_all_twelve_lessons_and_practice(client, monkeypatch, deepseek):
    from app.services.submission import PROBLEMS
    from app.services.problem_catalog import KNOWLEDGE
    observed = []
    install_cloud(monkeypatch, lambda request: cloud_reply(request, observed))
    headers = login(client)
    cases = json.loads((Path(__file__).parent / 'data/global_analysis_cases.json').read_text(encoding='utf-8'))
    expected_calls = 0
    for case in cases:
        lesson = PROBLEMS[case['problem_id']]
        code = case.get('code') or lesson.reference_solution.replace(*case['replace'], 1)
        data = submit_and_analyze(client, headers, json={'problem_id': lesson.problem_id, 'code': code})
        assert data['analysis']['status'] == 'ready', data['analysis']
        assert data['analysis']['source'] == 'ai'
        assert data['analysis']['model'] == 'deepseek-flash'
        assert data['analysis']['timings']['model_load_ms'] == 0
        partial = 0 < data['judge']['passed_cases'] < data['judge']['total_cases']
        if partial:
            expected_calls += 1
            assert data['analysis']['feedback_kind'] == 'guidance'
            assert data['analysis']['content'] is None
            assert data['analysis']['guidance']['knowledge_points'] == [KNOWLEDGE[lesson.knowledge_ids[0]].name]
            facts = observed[-1]
            assert 'public_cases' in facts
        else:
            expected_calls += 2
            assert data['analysis']['feedback_kind'] == 'diagnosis'
            assert data['analysis']['content']['knowledge_ids'] == lesson.knowledge_ids[:1]
            facts = observed[-2]
            assert facts['execution_mode'] == 'submit'
            assert 'candidate' in observed[-1], 'diagnosis review must also use the cloud model'
        assert facts['problem']['problem_id'] == lesson.problem_id
        assert 'reference_solution' not in facts['problem']
        public_ids = {test.case_id for test in lesson.tests if test.visibility == 'public'}
        assert all(item['case_id'] in public_ids for item in facts.get('allowed_evidence', []))
        assert 'hidden-' not in json.dumps(facts)
        assert 'PRIVATE_REASONING' not in json.dumps(data)
        assert client.post('/api/v1/code/submit', headers=headers, json={
            'problem_id': lesson.problem_id, 'code': lesson.reference_solution,
        }).json()['data']['judge']['passed']
    assert len(observed) == expected_calls
    practice = PROBLEMS['practice-01-1-v1']
    data = submit_and_analyze(client, headers, json={'problem_id': practice.problem_id, 'code': 'print("wrong")'})
    assert data['analysis']['model'] == 'deepseek-flash'
    assert data['analysis']['status'] == 'ready'
    record = client.get('/api/v1/code/submissions', headers=headers)
    assert record.status_code == 200
    assert 'PRIVATE_REASONING' not in record.text
    assert 'test-only-cloud-key' not in record.text


def test_run_error_uses_cloud_without_saving_a_submission(client, monkeypatch, deepseek):
    observed = []
    install_cloud(monkeypatch, lambda request: cloud_reply(request, observed))
    headers = login(client)
    result = client.post('/api/v1/code/run', headers=headers, json={'code': 'print(missing_value)'})
    data = result.json()['data']
    assert data['analysis']['status'] == 'ready'
    assert data['analysis']['model'] == 'deepseek-flash'
    assert observed[0]['execution_mode'] == 'run'
    assert client.get('/api/v1/code/submissions', headers=headers).json()['data']['total'] == 0


def test_missing_key_is_visible_instead_of_becoming_a_fixed_diagnosis(client, monkeypatch, deepseek):
    monkeypatch.setattr(deepseek, 'DEEPSEEK_API_KEY', '')
    install_cloud(monkeypatch, lambda request: pytest.fail('missing key must not call a model'))
    headers = login(client)
    for code in ['print(missing_value)', 'for i in range(3)\n    print(i)']:
        result = submit_and_analyze(client, headers, json={'problem_id': 'level1', 'code': code})
        assert result['judge']['passed'] is False
        assert result['analysis']['status'] == 'unavailable'
        assert result['analysis']['source'] is None
        assert result['analysis']['content'] is None
        assert 'DEEPSEEK_API_KEY' in result['analysis']['message']
    good = submit_and_analyze(client, headers, json={'problem_id': 'level1', 'code': "print('Hello, World!')"})
    assert good['judge']['passed'] and good['analysis']['status'] == 'skipped'


@pytest.mark.parametrize('status,notice', [(401, 'Key 无效'), (402, '余额不足'), (429, '限流'), (503, '服务暂不可用')])
def test_cloud_http_errors_remain_readable_and_never_expose_provider_body(client, monkeypatch, deepseek, status, notice):
    install_cloud(monkeypatch, lambda request: httpx.Response(status, json={'error': {'message': 'SECRET_PROVIDER_BODY'}}))
    result = submit_and_analyze(client, login(client), json={'problem_id': 'level1', 'code': 'print("wrong")'})
    assert result['analysis']['status'] == 'unavailable'
    assert result['analysis']['content'] is None
    assert notice in result['analysis']['message']
    assert 'SECRET_PROVIDER_BODY' not in json.dumps(result)


@pytest.mark.parametrize('body', [
    {'choices': []},
    {'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]},
    {'choices': [{'finish_reason': 'stop', 'message': {'content': None, 'reasoning_content': '{}'}}]},
    {'choices': [{'finish_reason': 'stop', 'message': {'content': 'not json'}}]},
])
def test_incomplete_or_invalid_cloud_output_is_not_replaced_with_fake_success(client, monkeypatch, deepseek, body):
    install_cloud(monkeypatch, lambda request: httpx.Response(200, json=body))
    result = submit_and_analyze(client, login(client), json={'problem_id': 'level1', 'code': 'print("wrong")'})
    assert result['analysis']['status'] == 'invalid_response'
    assert result['analysis']['content'] is None


def test_cloud_timeout_keeps_the_judge(client, monkeypatch, deepseek):
    def timeout(request):
        raise httpx.ReadTimeout('timeout', request=request)
    install_cloud(monkeypatch, timeout)
    result = submit_and_analyze(client, login(client), json={'problem_id': 'level1', 'code': 'print("wrong")'})
    assert result['judge']['status'] == 'wrong_answer'
    assert result['analysis']['status'] == 'timeout'


def test_cloud_json_with_fabricated_evidence_is_rejected(client, monkeypatch, deepseek):
    observed = []
    def reply(request):
        response = cloud_reply(request, observed)
        body = response.json()
        draft = json.loads(body['choices'][0]['message']['content'])
        draft['evidence'][0]['quote'] = 'THIS_OUTPUT_NEVER_OCCURRED'
        return completion(draft)
    install_cloud(monkeypatch, reply)
    result = submit_and_analyze(client, login(client), json={'problem_id': 'level1', 'code': 'print("wrong")'})
    assert result['analysis']['status'] == 'invalid_response'
    assert result['analysis']['content'] is None
    assert len(observed) == 1, 'fabricated evidence must be rejected before review'


def test_even_unredacted_judges_never_send_private_evidence(monkeypatch, deepseek):
    import asyncio
    from app.services.submission import PROBLEMS, judge_submission
    problem = PROBLEMS['greeting-v1'].execution_problem()
    judge = judge_submission(problem, 'print("wrong")')
    for case in judge.cases:
        if case.visibility == 'hidden':
            case.actual_output = 'PRIVATE_OUTPUT_SENTINEL'
    observed = []
    def reply(request):
        assert b'PRIVATE_OUTPUT_SENTINEL' not in request.content
        return cloud_reply(request, observed)
    install_cloud(monkeypatch, reply)
    result = asyncio.run(deepseek.analyze_failure(problem, 'print("wrong")', judge))
    assert result.status == 'ready'
    assert all(item['case_id'] == 'sample-1' for item in observed[0]['allowed_evidence'])


@pytest.mark.parametrize('stream', [False, True])
def test_chat_still_calls_ollama_without_cloud_credentials(client, monkeypatch, deepseek, stream):
    from app.api import ai
    monkeypatch.setattr(ai, 'LOCAL_LLM_URL', 'http://ollama.test/api/chat')
    observed = []
    def reply(request):
        payload = json.loads(request.content)
        observed.append(payload)
        assert str(request.url) == 'http://ollama.test/api/chat'
        assert 'Authorization' not in request.headers
        assert payload['model'] == ai.OLLAMA_MODEL
        assert 'response_format' not in payload
        assert 'Ottly' in payload['messages'][0]['content']
        if stream:
            return httpx.Response(200, text=json.dumps({'message': {'content': 'LOCAL_OTTLY_REPLY'}, 'done': True}) + '\n')
        return httpx.Response(200, json={'message': {'content': 'LOCAL_OTTLY_REPLY'}, 'done': True})
    install_cloud(monkeypatch, reply)
    response = client.post('/api/v1/ai/chat', headers=login(client), json={'question': '你是谁？', 'stream': stream})
    assert response.status_code == 200
    assert 'LOCAL_OTTLY_REPLY' in response.text
    assert len(observed) == 1
