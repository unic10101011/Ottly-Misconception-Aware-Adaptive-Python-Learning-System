"""Run only against a freshly provisioned ottly_security_test_* MySQL schema."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from sqlalchemy.engine import make_url
    url = make_url(os.environ['DATABASE_URL'])
    if url.get_backend_name() != 'mysql' or not (url.database or '').startswith('ottly_security_test_'):
        raise SystemExit('A dedicated ottly_security_test_* database is required.')
    os.environ['DEEPSEEK_API_KEY'] = ''
    os.environ['JWT_SECRET'] = secrets.token_urlsafe(48)
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    from main import app
    from app.api import coding
    from app.core.database import engine, SessionLocal
    from app.services.error_analysis import AnalysisResult
    nonce = secrets.token_hex(4)
    password = secrets.token_urlsafe(24)
    with TestClient(app) as client:
        def account(suffix):
            name = f'audit_{nonce}_{suffix}'
            registered = client.post('/api/v1/auth/register', json={
                'username': name, 'phone': name, 'password': password})
            assert registered.json()['code'] == 201, registered.text
            token = client.post('/api/v1/auth/login', json={'username': name, 'password': password}).json()['data']['access_token']
            return registered.json()['data']['id'], {'Authorization': 'Bearer ' + token}
        user_id, owner = account('a')
        _, other = account('b')
        weak = client.post('/api/v1/auth/change-password', headers=owner,
                           json={'current_password': password, 'new_password': ' ' * 12})
        assert weak.status_code == 422

        def submit(code):
            response = client.post('/api/v1/code/submit', headers=owner,
                                   json={'problem_id': 'level1', 'code': code})
            assert response.status_code == 200, response.text
            return response.json()['data']
        failed = submit('print("wrong")')
        path = f'/api/v1/code/submissions/{failed["submission_id"]}/analysis'
        assert client.post(path, headers=other).status_code == 404

        async def check_concurrent_analysis():
            entered, release = asyncio.Event(), asyncio.Event()
            calls = []
            async def model(*args, **kwargs):
                assert engine.pool.checkedout() == 0, 'Model wait retained a MySQL connection'
                calls.append(1)
                entered.set()
                await release.wait()
                return AnalysisResult(status='unavailable', message='mock-only')
            coding.analyze_failure = model
            with SessionLocal() as left, SessionLocal() as right:
                user = SimpleNamespace(id=user_id)
                task = asyncio.create_task(coding.prepare_analysis(failed['submission_id'], user, left))
                try:
                    await asyncio.wait_for(entered.wait(), 3)
                    try:
                        await coding.prepare_analysis(failed['submission_id'], user, right)
                    except HTTPException as error:
                        assert error.status_code == 409
                    else:
                        raise AssertionError('Duplicate AI request was not rejected')
                    assert engine.pool.checkedout() == 0
                finally:
                    release.set()
                    await task
            assert len(calls) == 1
        asyncio.run(check_concurrent_analysis())
        assert client.post(path, headers=owner).json()['data']['analysis']['status'] == 'unavailable'
        assert submit('print("Hello, World!")')['judge']['passed']

        async def unavailable(*args, **kwargs):
            assert engine.pool.checkedout() == 0
            return AnalysisResult(status='unavailable', message='mock-only')
        coding.analyze_failure = unavailable
        attack = 'import operator\ng = operator.attrgetter("__globals__")(input)\nprint(g)'
        run = client.post('/api/v1/code/run', headers=owner, json={'code': attack}).json()['data']
        assert not run['success'] and run['output'] == ''
        assert any(error['type'] == 'SECURITY_ERROR' for error in run['errors'])
        memory = client.post('/api/v1/code/run', headers=owner,
                             json={'code': 'data = bytearray(200 * 1024 * 1024)'}).json()['data']
        assert not memory['success']
        assert client.post('/api/v1/code/run', headers=owner, json={'code': 'print("healthy")'}).json()['data']['output'] == 'healthy\n'
        assert client.get('/api/v1/code/submissions', headers=other).json()['data']['total'] == 0
    engine.dispose()
    print(json.dumps({'mysql_security_smoke': 'passed', 'sandbox_rejection': 'passed',
                      'memory_recovery': 'passed', 'connection_release': 'passed',
                      'duplicate_ai_rejection': 'passed', 'account_isolation': 'passed',
                      'password_policy': 'passed'}))


if __name__ == '__main__':
    main()
