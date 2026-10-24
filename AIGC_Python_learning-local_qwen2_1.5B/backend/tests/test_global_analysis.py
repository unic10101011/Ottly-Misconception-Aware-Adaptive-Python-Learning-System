"""Shared analysis across curriculum, bank IDs and run-only executions."""
import json
import asyncio
from pathlib import Path

import httpx
import pytest

from test_submission import client, login, mock_model, model_facts, submit_and_analyze


def install_model(monkeypatch, observed):
    def generate(request):
        payload = json.loads(request.content)
        facts = model_facts(payload)
        observed.append((payload, facts))
        evidence = facts['allowed_evidence'][0]
        errors = [error['type'] for case in facts['failed_cases'] for error in case['errors']]
        cause = ('疑似引用了尚未定义的名字。' if 'NameError' in errors else
                 '疑似当前操作或数据不符合要求，请结合本次执行证据核对。')
        content = {
            'misconception_tag': 'other', 'suspected_cause': cause,
            'evidence': [{**evidence, 'explanation': '这是本次实际运行产生的公开结果。'}],
            'knowledge_points': ['输入与输出'],
        }
        return httpx.Response(200, json={'done': True, 'message': {'content': json.dumps(content)}})
    mock_model(monkeypatch, generate)


def test_all_lessons_and_an_unlisted_bank_id_share_the_same_analysis(client, monkeypatch):
    from app.services.submission import PROBLEMS
    observed = []
    install_model(monkeypatch, observed)
    headers = login(client)
    cases = json.loads((Path(__file__).parent / 'data/global_analysis_cases.json').read_text(encoding='utf-8'))
    for case in cases:
        lesson = PROBLEMS[case['problem_id']]
        code = case.get('code') or lesson.reference_solution.replace(*case['replace'], 1)
        data = submit_and_analyze(client, headers, json={'problem_id': lesson.problem_id, 'code': code})
        assert data['analysis']['status'] == 'ready', lesson.problem_id
        assert data['analysis']['source'] == 'ai', lesson.problem_id
        payload, facts = observed[-1]
        assert 'syntax_error' not in payload['format']['properties']['misconception_tag']['enum']
        assert facts['problem']['problem_id'] == lesson.problem_id
        assert 'reference_solution' not in facts['problem']
        assert facts['execution_mode'] == 'submit'
        assert facts['related_history'] == []
        assert 'hints' not in payload['format']['properties']
        if lesson.problem_id == 'shell-shop-v1':
            assert facts['failed_cases'][0]['output_lines'] == [
                {'line': 1, 'actual': '7', 'expected': '12', 'matches': False},
                {'line': 2, 'actual': '8', 'expected': '8', 'matches': True},
            ]
            assert '第 2 行输出已经正确' in facts['diagnosis_scope'][0]['focus']
        public = {test.case_id: test.stdin for test in lesson.tests if test.visibility == 'public'}
        assert all(item['case_id'] in public and item['stdin'] == public[item['case_id']]
                   for item in facts['failed_cases'])
        assert client.post('/api/v1/code/submit', headers=headers, json={
            'problem_id': lesson.problem_id, 'code': lesson.reference_solution,
        }).json()['data']['judge']['passed']
    bank = PROBLEMS['shell-shop-v1'].model_copy(update={
        'problem_id': 'bank-arithmetic-v1', 'prerequisite_problem_ids': [],
    })
    monkeypatch.setitem(PROBLEMS, bank.problem_id, bank)
    data = submit_and_analyze(client, headers, json={'problem_id': bank.problem_id, 'code': cases[2]['code']})
    assert data['analysis']['source'] == 'ai'
    assert observed[-1][1]['problem']['problem_id'] == bank.problem_id


@pytest.mark.parametrize('code,stdin,error_code', [
    ('price=int(input())', 'abc\n', 'VALUE_ERROR'),
    ('price=int(input())', '', 'EOF_ERROR'),
    ('print(missing_value)', '', 'NAME_ERROR'),
    ('if True\n    print(1)', '', 'SYNTAX_ERROR'),
])
def test_run_errors_use_real_input_once_without_creating_submissions(client, monkeypatch, code, stdin, error_code):
    from app.api import coding
    observed, runs = [], []
    install_model(monkeypatch, observed)
    execute = coding.run_code_process

    def counted(*args, **kwargs):
        runs.append(kwargs['stdin'])
        return execute(*args, **kwargs)

    monkeypatch.setattr(coding, 'run_code_process', counted)
    headers = login(client)
    response = client.post('/api/v1/code/run', headers=headers, json={'code': code, 'stdin': stdin, 'timeout': 3})
    assert response.status_code == 200, response.text
    data = response.json()['data']
    assert data['success'] is False
    assert data['errors'][0]['type'] == error_code
    assert data['analysis']['source'] == 'ai'
    assert runs == [stdin]
    payload, facts = observed[0]
    assert facts['execution_mode'] == 'run'
    assert facts['failed_cases'][0]['stdin'] == stdin
    assert facts['failed_cases'][0]['expected_output'] == ''
    assert facts['allowed_evidence'][0]['field'] == 'error_message'
    if error_code != 'SYNTAX_ERROR':
        assert 'syntax_error' not in payload['format']['properties']['misconception_tag']['enum']
    assert client.get('/api/v1/code/submissions', headers=headers).json()['data']['total'] == 0


def test_syntax_submission_also_requests_ai_when_configured(client, monkeypatch):
    observed = []
    install_model(monkeypatch, observed)
    headers = login(client)
    code = 'if True\n    print(1)'
    data = submit_and_analyze(client, headers, json={'problem_id': 'level1', 'code': code})
    assert data['analysis']['source'] == 'ai'
    assert 'syntax_error' in observed[0][0]['format']['properties']['misconception_tag']['enum']


def test_run_model_outage_preserves_error_and_successful_runs_skip_ai(client, monkeypatch):
    from app.api import coding
    calls = []

    async def unavailable(*args, **kwargs):
        calls.append(kwargs)
        raise RuntimeError('model unavailable')

    monkeypatch.setattr(coding, 'analyze_failure', unavailable)
    headers = login(client)
    good = client.post('/api/v1/code/run', headers=headers, json={'code': 'print(1)'}).json()['data']
    assert good['success'] and good['output'] == '1\n'
    assert 'analysis' not in good and calls == []
    bad = client.post('/api/v1/code/run', headers=headers, json={'code': 'print(missing_value)'}).json()['data']
    assert bad['errors'][0]['type'] == 'NAME_ERROR'
    assert bad['analysis']['status'] == 'unavailable'
    assert calls == [{'execution_mode': 'run'}]


def test_run_problem_context_obeys_lesson_access(client, monkeypatch):
    headers = login(client)
    response = client.post('/api/v1/code/run', headers=headers, json={
        'problem_id': 'shell-shop-v1', 'code': 'print(missing_value)',
    })
    assert response.status_code == 403


def test_streamed_run_exposes_real_error_before_model_without_rerunning(client, monkeypatch):
    from app.api import coding
    observed, runs = [], []
    install_model(monkeypatch, observed)
    execute = coding.run_code_process

    def counted(*args, **kwargs):
        runs.append(kwargs['stdin'])
        return execute(*args, **kwargs)

    monkeypatch.setattr(coding, 'run_code_process', counted)

    async def check():
        response = await coding.execute_code(coding.CodeRunRequest(code='print(missing_value)', stdin='actual input'),
                                             current_user=None, db=None, stream_analysis=True)
        first = json.loads(await anext(response.body_iterator))['data']
        assert first['analysis']['status'] == 'preparing'
        assert first['errors'][0]['type'] == 'NAME_ERROR'
        assert observed == [], 'error evidence must arrive before the model starts'
        final = json.loads(await anext(response.body_iterator))['data']
        assert final['analysis']['status'] == 'ready'
        assert final['analysis']['source'] == 'ai'
        assert final['judge'] == first['judge']
        assert runs == ['actual input']
        assert observed[0][1]['failed_cases'][0]['stdin'] == 'actual input'
        with pytest.raises(StopAsyncIteration):
            await anext(response.body_iterator)
    asyncio.run(check())
