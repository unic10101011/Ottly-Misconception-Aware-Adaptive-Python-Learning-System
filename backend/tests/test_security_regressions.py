"""Security failures are exercised without a live model or production database."""
import asyncio
from contextlib import ExitStack, contextmanager
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from test_submission import client, login


@pytest.mark.parametrize('code', [
    'import operator\ng = operator.attrgetter("__globals__")(input)\nprint(g)',
    'from operator import attrgetter\nprint(attrgetter("__self__")(input))',
    'getter = getattr\nprint(getter(input, "__globals__"))',
    'print("{0.__self__.safe_globals}".format(input))',
    'formatter = str.format\nprint(formatter("{0.__globals__}", input))',
    'print(__builtins__)',
    'g = (i for i in range(1))\nprint(g.gi_frame)',
    'T = type(input)\nmatch input:\n    case T(__self__=owner):\n        print(owner)',
    'from math import __loader__',
    'import math as __builtins__',
])
def test_runtime_introspection_is_rejected(code):
    from app.services.sandbox.runner import run_code_process
    result = run_code_process(code)
    assert not result['success'], result
    assert result['output'] == ''
    assert any(error['type'] == '安全警告' for error in result['errors'])


def test_allowed_math_input_functions_and_collections_still_work():
    from app.services.sandbox.runner import run_code_process
    result = run_code_process('from math import sqrt\ndef twice(n):\n    return n * 2\na = []\na.append(twice(int(input())))\nprint(a[0], int(sqrt(9)))', stdin='4\n')
    assert result['success'], result
    assert result['output'] == '8 3\n'


@pytest.mark.skipif(sys.platform != 'linux', reason='Hard memory limit is provided by the Linux Docker runtime')
def test_memory_exhaustion_is_confined_to_worker():
    from app.services.sandbox.runner import run_code_process
    result = run_code_process('data = bytearray(200 * 1024 * 1024)\nprint("unbounded")')
    assert not result['success']
    assert result['output'] == ''
    assert result['errors'][0]['type'] == 'MemoryError'
    assert run_code_process('print("healthy")')['output'] == 'healthy\n'


def test_run_and_replay_share_a_bounded_capacity_and_recover():
    from app.services.sandbox.limits import execution_slot
    from app.services.sandbox.runner import run_code_process
    from app.services.sandbox.trace_runner import run_trace_process
    with execution_slot(), execution_slot():
        assert run_code_process('print(1)')['errors'][0]['type'] == 'RunnerError'
        assert run_trace_process('print(1)', '')['trace_status'] == 'unavailable'
    assert run_code_process('print(1)')['output'] == '1\n'


@pytest.mark.parametrize('operation', ['analysis', 'recommendation'])
def test_duplicate_ai_work_is_rejected_and_wait_holds_no_connection(client, monkeypatch, operation):
    from app.api import coding
    from app.core.database import get_db
    from app.services.error_analysis import AnalysisResult
    from app.services.practice_recommendation import RecommendationResult
    headers = login(client)
    user_id = client.get('/api/v1/auth/me', headers=headers).json()['data']['id']
    submitted = client.post('/api/v1/code/submit', headers=headers,
                            json={'problem_id': 'level1', 'code': 'print("wrong")'}).json()['data']
    if operation == 'recommendation':
        submitted = client.post('/api/v1/code/submit', headers=headers,
                                json={'problem_id': 'level1', 'code': 'print("Hello, World!")'}).json()['data']
        assert submitted['practice_recommendation_eligible']
    with ExitStack() as stack:
        sessions = [stack.enter_context(contextmanager(client.app.dependency_overrides[get_db])()) for _ in range(2)]
        async def scenario():
            entered, release = asyncio.Event(), asyncio.Event()
            calls = []
            async def model(*args, **kwargs):
                calls.append(1)
                assert not sessions[0].in_transaction(), 'AI must not retain a database transaction'
                entered.set()
                await release.wait()
                return (AnalysisResult(status='unavailable', message='test-only') if operation == 'analysis'
                        else RecommendationResult(status='skipped'))
            monkeypatch.setattr(coding, 'analyze_failure' if operation == 'analysis' else 'recommend_practice', model)
            endpoint = coding.prepare_analysis if operation == 'analysis' else coding.prepare_practice_recommendation
            user = SimpleNamespace(id=user_id)
            task = asyncio.create_task(endpoint(submitted['submission_id'], user, sessions[0]))
            try:
                await asyncio.wait_for(entered.wait(), 3)
                with pytest.raises(HTTPException) as error:
                    await endpoint(submitted['submission_id'], user, sessions[1])
                assert error.value.status_code == 409
                assert not sessions[1].in_transaction()
            finally:
                release.set()
                await task
            await endpoint(submitted['submission_id'], user, sessions[1])
            assert len(calls) == 1, 'Reading the completed cache must not call the model again'
        asyncio.run(scenario())


def test_ai_capacity_is_released_after_errors():
    from app.services.ai_operations import ai_operation
    with ai_operation(999, 'analysis', 1), ai_operation(999, 'analysis', 2):
        with pytest.raises(HTTPException) as error:
            with ai_operation(999, 'analysis', 3):
                pytest.fail('Capacity must be bounded')
        assert error.value.status_code == 429
    with pytest.raises(RuntimeError):
        with ai_operation(999, 'analysis', 1):
            raise RuntimeError('model failed')
    with ai_operation(999, 'analysis', 1):
        pass


def test_chat_preparation_returns_connection_before_model_wait(client):
    from app.api import ai
    from app.core.database import get_db
    headers = login(client)
    user_id = client.get('/api/v1/auth/me', headers=headers).json()['data']['id']
    with contextmanager(client.app.dependency_overrides[get_db])() as db:
        async def scenario():
            session_id, messages = await ai.prepare_chat(ai.AIChatRequest(question='Python是什么？'), db, user_id)
            try:
                assert messages[-1]['content'] == 'Python是什么？'
                assert not db.in_transaction()
            finally:
                ai.pending_chats.pop((user_id, session_id), None)
        asyncio.run(scenario())


@pytest.mark.parametrize('password', ['short123', ' ' * 12, 'a' * 12, 'password1234', 'submission_student', '13800138000', 'x' * 129])
def test_password_change_enforces_registration_policy_without_echo(client, password):
    headers = login(client)
    response = client.post('/api/v1/auth/change-password', headers=headers,
                           json={'current_password': 'TestPass1234!', 'new_password': password})
    assert response.status_code == 422
    assert password not in response.text
    assert client.get('/api/v1/auth/me', headers=headers).status_code == 200
