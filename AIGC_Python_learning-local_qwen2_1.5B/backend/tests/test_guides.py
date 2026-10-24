"""Guide checks are durable, account scoped, and never code submissions."""
from test_learning_history import client, account


def test_guide_requires_auth_and_rejects_incomplete_or_wrong_answers(client):
    assert client.get('/api/v1/code/guides/level1').status_code == 401
    headers = account(client, 'guide_a', '13800000301')
    data = client.get('/api/v1/code/guides/level1', headers=headers).json()['data']
    assert data['completed'] is False
    story = data['story']
    assert story['problemId'] == 'level1'
    assert len([node for node in story['nodes'] if node['type'] == 'quiz']) == 3
    payload = {'version': story['id'], 'heard': ['quotes'], 'answers': {}}
    assert client.post('/api/v1/code/guides/level1/complete', headers=headers, json=payload).status_code == 422
    payload['answers'] = {node['id']: node['correct'] for node in story['nodes'] if node['type'] == 'quiz'}
    assert client.post('/api/v1/code/guides/level1/complete', headers=headers,
                       json={**payload, 'version': 'old-version'}).status_code == 422
    assert client.post('/api/v1/code/guides/level1/complete', headers=headers,
                       json={**payload, 'heard': []}).status_code == 422
    key = next(iter(payload['answers']))
    payload['answers'][key] = 'not-an-answer'
    assert client.post('/api/v1/code/guides/level1/complete', headers=headers, json=payload).status_code == 422
    assert client.get('/api/v1/code/guides/level1', headers=headers).json()['data']['completed'] is False
    assert client.get('/api/v1/code/guides/level2', headers=headers).status_code == 404
    assert client.get('/api/v1/code/guides/greeting-v1', headers=headers).status_code == 403


def test_completion_survives_reads_is_idempotent_and_isolated_without_judged_attempts(client):
    a = account(client, 'guide_owner', '13800000302')
    b = account(client, 'guide_other', '13800000303')
    story = client.get('/api/v1/code/guides/level1', headers=a).json()['data']['story']
    payload = {'version': story['id'], 'heard': ['quotes'],
               'answers': {node['id']: node['correct'] for node in story['nodes'] if node['type'] == 'quiz'}}
    for _ in range(2):
        response = client.post('/api/v1/code/guides/level1/complete', headers=a, json=payload)
        assert response.status_code == 200, response.text
        assert response.json()['data']['completed'] is True
    assert client.get('/api/v1/code/guides/level1', headers=a).json()['data']['completed'] is True
    assert client.get('/api/v1/code/guides/level1', headers=b).json()['data']['completed'] is False
    assert client.get('/api/v1/code/progress', headers=a).json()['data']['passed_problem_ids'] == []
    assert client.get('/api/v1/code/submissions', headers=a).json()['data']['total'] == 0
    assert client.get('/api/v1/code/submissions?failed_only=true', headers=a).json()['data']['total'] == 0


def test_every_formal_guide_can_finish_and_delete_account_clears_guide_rows(client, monkeypatch):
    from app.api import guides
    from app.core.database import get_db
    from app.models.guide_progress import GuideProgress
    from main import app
    headers = account(client, 'guide_all', '13800000304')
    # Simulate an already unlocked curriculum without creating judged attempts.
    monkeypatch.setattr(guides, 'passed_problem_ids', lambda db, user_id: set(guides.GUIDES))
    assert len(guides.GUIDES) == 12
    for pid, story in guides.GUIDES.items():
        data = client.get(f'/api/v1/code/guides/{pid}', headers=headers).json()['data']
        assert data['completed'] is False
        heard = next(node['options'][0]['id'] for node in story['nodes'] if node['type'] == 'choice')
        response = client.post(f'/api/v1/code/guides/{pid}/complete', headers=headers, json={
            'version': story['id'], 'heard': [heard],
            'answers': {node['id']: node['correct'] for node in story['nodes'] if node['type'] == 'quiz'},
        })
        assert response.status_code == 200, response.text
        assert client.get(f'/api/v1/code/guides/{pid}', headers=headers).json()['data']['completed'] is True
    with next(app.dependency_overrides[get_db]()) as db:
        assert db.query(GuideProgress).count() == 12
    assert client.request('DELETE', '/api/v1/auth/me', headers=headers,
                          json={'current_password': 'TestPass1234!'}).status_code == 200
    with next(app.dependency_overrides[get_db]()) as db:
        assert db.query(GuideProgress).count() == 0
