"""Isolated MySQL HTTP/persistence smoke test; never run on a project database."""
import json
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from sqlalchemy.engine import make_url
    url = make_url(os.environ['DATABASE_URL'])
    if url.get_backend_name() != 'mysql' or not (url.database or '').startswith('ottly_contract_test_'):
        raise SystemExit('A dedicated ottly_contract_test_* MySQL database is required.')
    os.environ['LOCAL_LLM_URL'] = ''
    os.environ.setdefault('JWT_SECRET', secrets.token_urlsafe(48))
    from fastapi.testclient import TestClient
    from main import app
    nonce = secrets.token_hex(4)
    password = secrets.token_urlsafe(24)
    with TestClient(app) as client:
        def account(suffix):
            body = {'username':f'contract_{nonce}_{suffix}', 'phone':f'test_{nonce}_{suffix}', 'password':password}
            assert client.post('/api/v1/auth/register', json=body).json()['code'] == 201
            token = client.post('/api/v1/auth/login', json=body).json()['data']['access_token']
            return {'Authorization':'Bearer ' + token}
        headers = account('a')
        def submit(problem_id, code, extra=None):
            response = client.post('/api/v1/code/submit', headers={**headers, **(extra or {})},
                                   json={'problem_id':problem_id, 'code':code})
            assert response.status_code == 200, response.text
            return response.json()
        locked = client.get('/api/v1/code/problems/greeting-v1', headers=headers)
        assert locked.status_code == 403
        offline = submit('level2', 'print(0)')
        assert offline['data']['analysis']['status'] == 'unavailable'
        first = submit('level1', "print('Hello, World!')")
        wrong = submit('greeting-v1', 'print("Hello, Ottly!")')
        execution_error = submit('greeting-v1', 'print(missing_name)')
        correct_code = 'name = input()\nprint("Hello,", name + "!")'
        correct = submit('greeting-v1', correct_code)
        review = submit('greeting-v1', correct_code, {'X-Review-Source-Id':str(wrong['data']['submission_id'])})
        assert correct['data']['judge']['passed']
        assert correct['data']['analysis']['source'] is None
        assert execution_error['data']['error_type'] == 'NAME_ERROR'
        assert wrong['data']['judge']['failed_tests'] == ['hidden-1','hidden-2','hidden-3']
        assert wrong['data']['analysis']['source'] == 'fixed'
        assert wrong['data']['analysis']['content']['knowledge_ids'] == ['K02']
        assert 'Sea Otter' not in json.dumps(wrong, ensure_ascii=False)
        history = client.get('/api/v1/code/submissions', headers=headers).json()['data']['items']
        assert len(history) == 6
        assert all(row['schema_version'] == '1.0.0' and row['version'] == 1 for row in history)
        assert history[0]['review_source_id'] == wrong['data']['submission_id']
        mistakes = client.get('/api/v1/code/mistakes', headers=headers).json()['data']['items']
        greeting = next(item for item in mistakes if item['problem_id'] == 'greeting-v1')
        assert len(mistakes) == 2 and greeting['review_count'] == 1
        other = account('b')
        assert client.get('/api/v1/code/submissions', headers=other).json()['data']['total'] == 0
        examples = {
            'schema_version':'1.0.0',
            'note':'Generated against isolated MySQL with fixed hint fallback; IDs/times are example values, not model quality results.',
            'accepted':correct, 'wrong_answer_hidden_cases':wrong, 'execution_error':execution_error,
            'model_unavailable':offline,
            'history':history,
        }
        if len(sys.argv) == 2:
            destination = Path(sys.argv[1])
            destination.write_text(json.dumps(examples, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'mysql_http_smoke':'passed','submissions':6,'snapshot_and_review':'passed','account_isolation':'passed'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
