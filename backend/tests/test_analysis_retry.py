from test_greeting import client, account, submit


def test_failed_analysis_retries_same_submission_and_caches_success(client, monkeypatch):
    from app.api import coding
    from app.services.error_analysis import AnalysisResult
    calls = []

    async def analyze(*args, **kwargs):
        calls.append(1)
        return AnalysisResult(status='timeout' if len(calls) == 1 else 'ready', message='test')

    monkeypatch.setattr(coding, 'analyze_failure', analyze)
    headers = account(client)
    data = submit(client, headers, 'level1', 'print(0)').json()['data']
    url = f"/api/v1/code/submissions/{data['submission_id']}/analysis"
    assert client.post(url, headers=headers).json()['data']['analysis']['status'] == 'timeout'
    assert client.post(url, headers=headers).json()['data']['analysis']['status'] == 'ready'
    assert client.post(url, headers=headers).json()['data']['analysis']['status'] == 'ready'
    assert len(calls) == 2
    assert client.get('/api/v1/code/submissions', headers=headers).json()['data']['total'] == 1


def test_run_analysis_retry_uses_owned_evidence_without_executing_again(client, monkeypatch):
    from app.api import coding
    from app.services.error_analysis import AnalysisResult
    async def analyze(*args, **kwargs):
        return AnalysisResult(status='timeout', message='timeout')
    monkeypatch.setattr(coding, 'analyze_failure', analyze)
    headers = account(client)
    run = client.post('/api/v1/code/run', headers=headers, json={'code': 'print(missing)'}).json()['data']
    assert run.get('analysis_id')
    def unexpected(*args, **kwargs):
        raise AssertionError('retry must not execute code')
    monkeypatch.setattr(coding, 'run_code_process', unexpected)
    url = '/api/v1/code/run-analysis/' + run['analysis_id']
    assert client.post(url, headers=headers).json()['data']['analysis']['status'] == 'timeout'
    other = account(client, 'other_student', '13900000002')
    assert client.post(url, headers=other).status_code == 404
    assert client.get('/api/v1/code/submissions', headers=headers).json()['data']['total'] == 0
    coding.run_analyses[run['analysis_id']]['created'] -= 1801
    assert client.post(url, headers=headers).status_code == 404
