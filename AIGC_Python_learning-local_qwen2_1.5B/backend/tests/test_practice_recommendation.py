import json
from pathlib import Path

import httpx
import pytest

from test_submission import client, login


@pytest.fixture
def cloud(monkeypatch):
    from app.services import error_analysis
    monkeypatch.setattr(error_analysis, 'ANALYSIS_PROVIDER', 'deepseek')
    monkeypatch.setattr(error_analysis, 'DEEPSEEK_API_KEY', 'recommendation-test-key')
    monkeypatch.setattr(error_analysis, 'DEEPSEEK_BASE_URL', 'https://deepseek.test')
    monkeypatch.setattr(error_analysis, 'DEEPSEEK_MODEL', 'deepseek-flash')


def install_choice(monkeypatch, calls, choose=None):
    factory = httpx.AsyncClient
    def respond(request):
        payload = json.loads(request.content)
        facts = json.JSONDecoder().raw_decode(payload['messages'][1]['content'])[0]
        calls.append(facts)
        assert str(request.url) == 'https://deepseek.test/chat/completions'
        assert request.headers['Authorization'] == 'Bearer recommendation-test-key'
        assert payload['model'] == 'deepseek-flash'
        assert all(case['visibility'] == 'public' for case in facts['failure']['public_cases'])
        assert all('tests' not in item and 'reference_solution' not in item for item in facts['candidates'])
        selected = choose(facts) if choose else facts['candidates'][-1]['problem_id']
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps({'problem_id': selected, 'reason': '这道题能帮你巩固刚才容易混淆的输出格式。'}),
        }}]})
    monkeypatch.setattr(httpx, 'AsyncClient',
                        lambda **kwargs: factory(transport=httpx.MockTransport(respond), **kwargs))


def submit(client, headers, problem_id='level1', code='print("Hello, World!")'):
    response = client.post('/api/v1/code/submit', headers=headers, json={'problem_id': problem_id, 'code': code})
    assert response.status_code == 200, response.text
    return response.json()['data']


def recommendation(client, headers, submission_id):
    return client.post(f'/api/v1/code/submissions/{submission_id}/practice-recommendation', headers=headers)


def corrected(client, headers):
    wrong = submit(client, headers, code='print("wrong")')
    assert wrong['judge']['passed'] is False
    accepted = submit(client, headers)
    assert accepted['judge']['passed'] and accepted['practice_recommendation_eligible']
    return wrong, accepted


def test_first_try_pass_and_failed_submissions_never_call_the_recommender(client, monkeypatch, cloud):
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: pytest.fail('no recommendation expected'))
    headers = login(client)
    accepted = submit(client, headers)
    assert accepted['practice_recommendation_eligible'] is False
    assert recommendation(client, headers, accepted['submission_id']).json()['data']['status'] == 'skipped'
    wrong = submit(client, headers, code='print("wrong")')
    assert wrong['practice_recommendation_eligible'] is False
    assert recommendation(client, headers, wrong['submission_id']).json()['data']['status'] == 'skipped'


def test_corrected_pass_selects_one_real_question_and_caches_the_ai_choice(client, monkeypatch, cloud):
    calls = []
    install_choice(monkeypatch, calls)
    headers = login(client)
    wrong, accepted = corrected(client, headers)
    assert calls == [], 'judging must finish before asking the model for practice'
    data = recommendation(client, headers, accepted['submission_id']).json()['data']
    assert data['status'] == 'ready'
    selected = data['recommendation']
    assert selected['problem_id'] == 'practice-01-3-v1', 'use the model choice, not the first candidate'
    assert selected['level_no'] == 1 and selected['model'] == 'deepseek-flash'
    assert calls[0]['failure']['code'] == 'print("wrong")'
    assert calls[0]['failure']['problem_id'] == wrong['problem_id']
    assert recommendation(client, headers, accepted['submission_id']).json()['data'] == data
    assert len(calls) == 1
    assert submit(client, headers)['practice_recommendation_eligible'] is False
    # An additional wrong -> correct cycle may recommend again, but a repeated pass does not.
    _, next_pass = corrected(client, headers)
    assert next_pass['practice_recommendation_eligible']


def test_recommendations_are_owned_by_the_authenticated_student(client, monkeypatch, cloud):
    calls = []
    install_choice(monkeypatch, calls)
    owner = login(client)
    _, accepted = corrected(client, owner)
    assert recommendation(client, {}, accepted['submission_id']).status_code == 401
    account = {'username': 'other_recommendation_user', 'password': 'TestPass1234!', 'phone': '13800000081'}
    client.post('/api/v1/auth/register', json=account)
    token = client.post('/api/v1/auth/login', json=account).json()['data']['access_token']
    assert recommendation(client, {'Authorization': 'Bearer ' + token}, accepted['submission_id']).status_code == 404
    assert calls == []


def test_only_unpassed_published_and_unlocked_related_exercises_are_candidates(client, monkeypatch, cloud):
    from app.services.problem_catalog import PROBLEMS
    calls = []
    install_choice(monkeypatch, calls)
    headers = login(client)
    submit(client, headers)
    practice = PROBLEMS['practice-01-2-v1']
    done = submit(client, headers, practice.problem_id, practice.reference_solution)
    assert done['judge']['passed'] and not done['practice_recommendation_eligible']
    monkeypatch.setitem(PROBLEMS, 'practice-01-1-v1', PROBLEMS['practice-01-1-v1'].model_copy(update={'published': False}))
    monkeypatch.setitem(PROBLEMS, 'locked-practice', practice.model_copy(update={
        'problem_id': 'locked-practice', 'prerequisite_problem_ids': ['greeting-v1'],
    }))
    _, accepted = corrected(client, headers)
    result = recommendation(client, headers, accepted['submission_id']).json()['data']
    assert result['status'] == 'ready'
    assert [item['problem_id'] for item in calls[0]['candidates']] == ['practice-01-3-v1']


def test_all_related_practice_completed_skips_without_a_model_call(client, monkeypatch, cloud):
    from app.services.problem_catalog import PROBLEMS
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: pytest.fail('nothing left to recommend'))
    headers = login(client)
    submit(client, headers)
    for index in range(1, 4):
        item = PROBLEMS[f'practice-01-{index}-v1']
        assert submit(client, headers, item.problem_id, item.reference_solution)['judge']['passed']
    _, accepted = corrected(client, headers)
    data = recommendation(client, headers, accepted['submission_id']).json()['data']
    assert data['status'] == 'skipped' and data['recommendation'] is None


@pytest.mark.parametrize('failure', ['http', 'timeout', 'invented_id', 'invalid_json'])
def test_recommendation_failure_never_changes_a_saved_pass(client, monkeypatch, cloud, failure):
    factory = httpx.AsyncClient
    def reply(request):
        if failure == 'http':
            return httpx.Response(402, json={'error': 'PRIVATE_PROVIDER_MESSAGE'})
        if failure == 'timeout':
            raise httpx.ReadTimeout('timeout', request=request)
        content = ('not JSON' if failure == 'invalid_json' else json.dumps({
            'problem_id': 'invented-by-model', 'reason': '这是一道题。',
        }))
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': content}}]})
    monkeypatch.setattr(httpx, 'AsyncClient',
                        lambda **kwargs: factory(transport=httpx.MockTransport(reply), **kwargs))
    headers = login(client)
    _, accepted = corrected(client, headers)
    data = recommendation(client, headers, accepted['submission_id']).json()['data']
    assert data['status'] == 'unavailable' and data['recommendation'] is None
    assert 'PRIVATE_PROVIDER_MESSAGE' not in json.dumps(data)
    assert client.get('/api/v1/code/levels', headers=headers).json()['data']['items'][0]['status'] == 'completed'
    history = client.get('/api/v1/code/submissions', headers=headers).json()['data']['items']
    assert history[0]['passed'] and history[0]['analysis']['status'] == 'skipped'


def test_each_of_the_twelve_main_lessons_can_recommend_after_a_correction(client, monkeypatch, cloud):
    from app.services.problem_catalog import PROBLEMS
    calls = []
    install_choice(monkeypatch, calls)
    headers = login(client)
    cases = json.loads((Path(__file__).parent / 'data/global_analysis_cases.json').read_text(encoding='utf-8'))
    for case in cases:
        lesson = PROBLEMS[case['problem_id']]
        code = case.get('code') or lesson.reference_solution.replace(*case['replace'], 1)
        assert not submit(client, headers, lesson.problem_id, code)['judge']['passed']
        accepted = submit(client, headers, lesson.problem_id, lesson.reference_solution)
        assert accepted['practice_recommendation_eligible'], lesson.problem_id
        result = recommendation(client, headers, accepted['submission_id']).json()['data']
        assert result['status'] == 'ready', result
        assert result['recommendation']['level_no'] == lesson.level_no
        if lesson.level_no in (3, 4, 5):
            new_ids = {f'practice-{lesson.level_no:02d}-{number}-v1' for number in (4, 5, 6)}
            assert new_ids.issubset({item['problem_id'] for item in calls[-1]['candidates']})
            assert result['recommendation']['problem_id'] in new_ids
    assert len(calls) == 12
