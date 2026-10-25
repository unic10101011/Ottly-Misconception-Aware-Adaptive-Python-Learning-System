"""The new second lesson keeps old submissions stable and works without AI."""
import json
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client(tmp_path, monkeypatch):
    os.environ.setdefault('DATABASE_URL', 'sqlite://')
    os.environ.setdefault('JWT_SECRET', 'greeting-test-secret')
    from main import app
    from app.core.database import Base, get_db
    from app.services import error_analysis

    engine = create_engine(f"sqlite:///{(tmp_path / 'greeting.sqlite').as_posix()}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    monkeypatch.setattr(error_analysis, 'LOCAL_LLM_URL', '')
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def account(client, name='greeting_student', phone='13900000001'):
    body = {'username': name, 'password': 'TestPass1234!', 'phone': phone}
    assert client.post('/api/v1/auth/register', json=body).json()['code'] == 201
    token = client.post('/api/v1/auth/login', json=body).json()['data']['access_token']
    return {'Authorization': 'Bearer ' + token}


def submit(client, headers, problem_id, code):
    return client.post('/api/v1/code/submit', headers=headers,
                       json={'problem_id': problem_id, 'code': code})


def test_six_step_flow_and_progress_survive_relogin(client):
    from app.services.submission import GREETING, GREETING_ID
    headers = account(client)
    url = '/api/v1/code/problems/' + GREETING_ID
    assert client.get(url).status_code == 401
    assert client.get(url, headers=headers).status_code == 403
    assert submit(client, headers, GREETING_ID, 'print(0)').status_code == 403
    assert client.get('/api/v1/code/levels', headers=headers).json()['data']['items'][1]['status'] == 'locked'
    assert submit(client, headers, 'level1', 'print("Hello, World!")').json()['data']['judge']['passed']
    lesson = client.get(url, headers=headers).json()['data']
    assert lesson['completed'] is False
    assert lesson['story'] and lesson['teaching'] and lesson['examples']
    assert not {'tests', 'hints', 'reference_solution'} & lesson.keys()
    assert client.get(url + '/solution', headers=headers).status_code == 403

    run = client.post('/api/v1/code/run', headers=headers, json={
        'code': GREETING['reference_solution'], 'stdin': 'Sea Otter\n', 'timeout': 3,
    }).json()['data']
    assert run['success'] and run['output'] == 'Hello, Sea Otter!\n'
    assert client.get(url, headers=headers).json()['data']['completed'] is False
    assert client.get('/api/v1/code/submissions', headers=headers).json()['data']['total'] == 1

    # Writing the sample answer passes only the public case, not the lesson.
    failed = submit(client, headers, GREETING_ID, 'print("Hello, Ottly!")').json()['data']
    assert failed['judge']['passed_cases'] == 1
    assert failed['judge']['total_cases'] == 4
    assert failed['analysis']['status'] == 'preparing'
    analyzed = client.post(f"/api/v1/code/submissions/{failed['submission_id']}/analysis", headers=headers)
    assert analyzed.status_code == 200, analyzed.text
    failed['analysis'] = analyzed.json()['data']['analysis']
    assert failed['analysis']['feedback_kind'] == 'guidance'
    assert failed['analysis']['source'] is None
    assert failed['analysis']['status'] == 'unavailable'
    assert failed['analysis']['content'] is None
    for name in ('Amy', 'Sea Otter', '小海獭'):
        assert name not in json.dumps(failed, ensure_ascii=False)
    for case in failed['judge']['cases'][1:]:
        assert case['visibility'] == 'hidden'
        assert case['actual_output'] == case['expected_output'] == ''
        assert case['errors'] == []
    for level in (1, 2, 3):
        result = client.patch(f"/api/v1/code/submissions/{failed['submission_id']}/hints",
                              headers=headers, json={'level': level})
        assert result.status_code == 409

    accepted = submit(client, headers, GREETING_ID, GREETING['reference_solution']).json()['data']
    assert accepted['judge']['passed'] and accepted['judge']['passed_cases'] == 4
    assert accepted['analysis']['status'] == 'skipped'
    assert client.get(url + '/solution', headers=headers).json()['data']['reference_solution'] == GREETING['reference_solution']
    # A later failure must not revoke completion.
    submit(client, headers, GREETING_ID, 'print(0)')
    token = client.post('/api/v1/auth/login', json={
        'username': 'greeting_student', 'password': 'TestPass1234!',
    }).json()['data']['access_token']
    renewed = {'Authorization': 'Bearer ' + token}
    assert client.get(url, headers=renewed).json()['data']['completed'] is True
    levels = client.get('/api/v1/code/levels', headers=renewed).json()['data']['items']
    assert levels[1]['status'] == 'completed'
    assert levels[2]['status'] == 'current' and levels[2]['published'] is True
    history = client.get('/api/v1/code/submissions?problem_id=' + GREETING_ID, headers=renewed).json()['data']
    old = next(item for item in history['items'] if item['id'] == failed['submission_id'])
    assert old['hints_viewed_max'] == 0 and old['resolved_later'] is True
    assert 'Sea Otter' not in json.dumps(history, ensure_ascii=False)
    second = account(client, 'greeting_other', '13900000002')
    assert client.get(url, headers=second).status_code == 403
    assert client.get(url + '/solution', headers=second).status_code == 403
    assert client.get('/api/v1/code/submissions', headers=second).json()['data']['total'] == 0


def test_legacy_loop_success_does_not_complete_greeting(client):
    headers = account(client)
    assert submit(client, headers, 'level2', 'print(5050)').json()['data']['judge']['passed']
    levels = client.get('/api/v1/code/levels', headers=headers).json()['data']['items']
    assert levels[1]['status'] == 'locked'


@pytest.mark.parametrize('code', [
    'name = input()\nprint("Hello,", "name!")',
    'name = input()\nprint("Hello,  " + name + "!")',
    'name = input()\nprint("Hello, " + name + "! ")',
    'name = input("姓名：")\nprint("Hello,", name + "!")',
    'name = input()\nprint("Hello,", name + "!"',
])
def test_greeting_rejects_mistakes(code):
    from app.services.submission import PROBLEMS, GREETING_ID, judge_submission
    assert not judge_submission(PROBLEMS[GREETING_ID], code).passed


def test_controlled_input_preserves_spaces_blank_lines_and_ends_at_eof():
    from app.services.sandbox.runner import run_code_process
    result = run_code_process('print(repr(input()))\nprint(repr(input()))', stdin=' a \r\n\r\n')
    assert result['success'] and result['output'] == "' a '\n''\n"
    result = run_code_process('print(input())\nprint(input())', stdin='only one\n')
    assert not result['success'] and result['errors'][0]['type'] == 'EOFError'
    assert result['output'] == 'only one\n'


def test_runner_outage_does_not_create_learning_failure(client, monkeypatch):
    from app.api import coding
    from app.services.submission import CaseResult, ExecutionError, JudgeResult
    headers = account(client)
    def outage(*args):
        return JudgeResult(status='execution_error', passed=False, passed_cases=0, total_cases=1,
            cases=[CaseResult(case_id='sample-1', passed=False, expected_output='', actual_output='',
                              errors=[ExecutionError(type='RunnerError', message='unavailable')], execution_time=0)])
    monkeypatch.setattr(coding, 'judge_submission', outage)
    assert submit(client, headers, 'level1', 'print(0)').status_code == 503
    assert client.get('/api/v1/code/submissions', headers=headers).json()['data']['total'] == 0
