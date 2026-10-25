import json

import httpx
import pytest

from test_submission import client, login


def draft(**updates):
    data = dict(
        title='灯塔补给', story='Ottly 每天给灯塔运送补给。', task='计算从第 1 天到第 n 天的补给总数。',
        input_format='一行一个整数 n。', output_format='一行输出总数。', constraints='0 <= n <= 10；n 为 0 时总数为 0。',
        knowledge_ids=['K07', 'K08'], target_misconception_tags=['accumulation_error'], difficulty=1,
        focus='循环中保留之前的累计值。',
        examples=[{'stdin': '3\n', 'stdout': '6\n'}],
        hidden_tests=[{'stdin': '0\n', 'stdout': '0\n'}, {'stdin': '1\n', 'stdout': '1\n'},
                      {'stdin': '10\n', 'stdout': '55\n'}],
        reference_solution='n = int(input())\ntotal = 0\nfor i in range(1, n + 1):\n    total += i\nprint(total)\n',
        solution_explanation='从 1 到 n 逐个累加，n 为零时循环不执行。',
    )
    return {**data, **updates}


def review(**updates):
    return {'approved': True, 'issues': [], 'boundary_cases': [
        {'stdin': '2\n', 'stdout': '3\n'}, {'stdin': '9\n', 'stdout': '45\n'},
    ], **updates}


def unlock(client, headers):
    from app.core.database import get_db
    from main import app
    from app.models.learning_submission import LearningSubmission
    from app.models.user import User
    from app.services.problem_catalog import LEVELS
    with next(app.dependency_overrides[get_db]()) as db:
        user = db.query(User).filter_by(username='submission_student').one()
        for slot in LEVELS:
            db.add(LearningSubmission(user_id=user.id, problem_id=slot.problem_id,
                                     problem_title='已完成', problem_description='已完成', code='print(1)',
                                     judge_json={}, passed=True))
        db.commit()


def saved_questions():
    from app.core.database import get_db
    from app.models.generated_problem import GeneratedProblem
    from main import app
    with next(app.dependency_overrides[get_db]()) as db:
        return db.query(GeneratedProblem).all()


def events(response):
    assert response.status_code == 200
    return [json.loads(line)['data'] for line in response.text.splitlines()]


def mock_model(monkeypatch, candidates=None, audited=None):
    from app.services import endless, error_analysis
    monkeypatch.setattr(error_analysis, 'analysis_configuration_error', lambda: None)
    calls = []
    async def generate(profile, previous_error):
        calls.append((profile, previous_error))
        value = candidates[len(calls) - 1] if candidates else draft()
        return json.dumps(value)
    async def audit(candidate):
        return endless.Review.model_validate(audited or review())
    monkeypatch.setattr(endless, 'generate_candidate', generate)
    monkeypatch.setattr(endless, 'review_candidate', audit)
    return calls


def test_both_modes_require_login_and_all_twelve_levels(client):
    assert client.post('/api/v1/code/endless', json={'mode': 'catalog'}).status_code == 401
    owner = login(client)
    for mode in ('catalog', 'ottly'):
        assert client.post('/api/v1/code/endless', headers=owner, json={'mode': mode}).status_code == 403
    assert saved_questions() == []


def test_catalog_draw_uses_only_existing_practice_and_no_model(client, monkeypatch):
    from app.services import endless
    from app.services.problem_catalog import PROBLEMS
    owner = login(client)
    unlock(client, owner)
    monkeypatch.setattr(endless, 'generate_candidate', lambda *args: pytest.fail('catalog does not call AI'))
    response = client.post('/api/v1/code/endless', headers=owner, json={'mode': 'catalog'})
    selected = response.json()['data']['problem_id']
    assert PROBLEMS[selected].kind == 'practice'
    assert client.get(f'/api/v1/code/problems/{selected}', headers=owner).status_code == 200
    assert saved_questions() == []


def test_verified_question_persists_uses_standard_judge_and_is_private(client, monkeypatch):
    from app.services.problem_catalog import PROBLEMS
    owner = login(client)
    unlock(client, owner)
    mock_model(monkeypatch)
    stream = events(client.post('/api/v1/code/endless', headers=owner, json={'mode': 'ottly'}))
    assert [item['stage'] for item in stream] == ['generating', 'structure', 'executing', 'reviewing', 'ready']
    problem_id = stream[-1]['problem_id']
    assert problem_id not in PROBLEMS, 'private questions must not mutate the shared catalog'
    assert len(saved_questions()) == 1
    assert len(saved_questions()[0].lesson_json['tests']) == 6
    listing = client.get('/api/v1/code/practice', headers=owner).json()['data']['items']
    entry = next(item for item in listing if item['problem_id'] == problem_id)
    assert entry['kind'] == entry['category'] == 'endless'
    assert entry['available'] and not entry['completed']
    assert not {'tests', 'reference_solution', 'lesson_json'} & entry.keys()
    assert listing[-1]['problem_id'] == problem_id
    filtered = client.get('/api/v1/code/practice?level_no=8', headers=owner).json()['data']['items']
    assert all(item['kind'] == 'practice' for item in filtered)
    detail = client.get(f'/api/v1/code/problems/{problem_id}', headers=owner).json()['data']
    assert detail['title'] == '灯塔补给' and detail['kind'] == 'endless'
    assert '数据范围' in detail['description']
    assert not {'tests', 'reference_solution', 'hints'} & detail.keys()
    assert 'reference_solution' not in json.dumps(stream)
    assert client.get(f'/api/v1/code/problems/{problem_id}/solution', headers=owner).status_code == 403
    failed = client.post('/api/v1/code/submit', headers=owner,
                         json={'problem_id': problem_id, 'code': 'print(0)'}).json()['data']
    assert not failed['judge']['passed']
    for case in failed['judge']['cases']:
        if case['visibility'] == 'hidden':
            assert case['expected_output'] == '' and case['actual_output'] == ''
    assert client.get('/api/v1/code/mistakes', headers=owner).json()['data']['items'][0]['source'] == 'Ottly 出题'
    from app.api import coding
    from app.services.error_analysis import AnalysisResult
    async def analyze(problem, code, judge, **kwargs):
        assert problem.problem_id == problem_id
        assert all(not case.expected_output for case in judge.cases if case.visibility == 'hidden')
        return AnalysisResult(status='unavailable', message='测试不调用真实模型')
    monkeypatch.setattr(coding, 'analyze_failure', analyze)
    assert client.post(f"/api/v1/code/submissions/{failed['submission_id']}/analysis", headers=owner).status_code == 200
    accepted = client.post('/api/v1/code/submit', headers=owner, json={
        'problem_id': problem_id, 'code': draft()['reference_solution'],
    }).json()['data']
    assert accepted['judge']['passed'] and not accepted['practice_recommendation_eligible']
    assert next(item for item in client.get('/api/v1/code/practice', headers=owner).json()['data']['items']
                if item['problem_id'] == problem_id)['completed']
    assert client.get(f'/api/v1/code/problems/{problem_id}', headers=owner).json()['data']['completed']
    assert client.get(f'/api/v1/code/problems/{problem_id}/solution', headers=owner).status_code == 200
    run = client.post('/api/v1/code/run', headers=owner,
                      json={'problem_id': problem_id, 'code': draft()['reference_solution'], 'stdin': '2\n'})
    assert run.json()['data']['output'] == '3\n'
    account = {'username': 'another_student', 'password': 'OtherPassword12!', 'phone': '13900000000'}
    client.post('/api/v1/auth/register', json=account)
    other = {'Authorization': 'Bearer ' + client.post('/api/v1/auth/login', json=account).json()['data']['access_token']}
    assert all(item['problem_id'] != problem_id for item in
               client.get('/api/v1/code/practice', headers=other).json()['data']['items'])
    for suffix in ('', '/solution'):
        assert client.get(f'/api/v1/code/problems/{problem_id}{suffix}', headers=other).status_code == 404
    for path, body in [('submit', {'problem_id': problem_id, 'code': 'print(0)'}),
                       ('run', {'problem_id': problem_id, 'code': 'print(0)'})]:
        assert client.post('/api/v1/code/' + path, headers=other, json=body).status_code == 404


@pytest.mark.parametrize('invalid', ['structure', 'reference', 'review', 'boundary'])
def test_invalid_candidates_retry_but_never_publish(client, monkeypatch, invalid):
    owner = login(client)
    unlock(client, owner)
    candidate, audited = draft(), review()
    if invalid == 'structure':
        candidate['knowledge_ids'] = ['K99']
    elif invalid == 'reference':
        candidate['reference_solution'] = 'print(999)'
    elif invalid == 'review':
        audited.update(approved=False, issues=['题意与边界不一致'])
    else:
        audited['boundary_cases'][0]['stdout'] = '999\n'
    calls = mock_model(monkeypatch, [candidate, candidate], audited)
    stream = events(client.post('/api/v1/code/endless', headers=owner, json={'mode': 'ottly'}))
    assert stream[-1]['stage'] == 'error'
    assert not any(item['stage'] == 'ready' for item in stream)
    assert len(calls) == 2 and calls[1][1]
    assert saved_questions() == []


def test_regeneration_can_recover_after_a_rejected_candidate(client, monkeypatch):
    owner = login(client)
    unlock(client, owner)
    calls = mock_model(monkeypatch, [draft(knowledge_ids=['K99']), draft()])
    stream = events(client.post('/api/v1/code/endless', headers=owner, json={'mode': 'ottly'}))
    assert stream[-1]['stage'] == 'ready'
    assert len(calls) == 2 and len(saved_questions()) == 1


def test_model_network_failure_keeps_catalog_available_and_creates_no_question(client, monkeypatch):
    from app.services import endless
    owner = login(client)
    unlock(client, owner)
    mock_model(monkeypatch)
    async def unavailable(*args):
        raise httpx.ConnectError('offline')
    monkeypatch.setattr(endless, 'generate_candidate', unavailable)
    stream = events(client.post('/api/v1/code/endless', headers=owner, json={'mode': 'ottly'}))
    assert stream[-1]['stage'] == 'error' and saved_questions() == []
    assert client.post('/api/v1/code/endless', headers=owner, json={'mode': 'catalog'}).status_code == 200


def test_generated_questions_are_removed_with_the_account(client, monkeypatch):
    owner = login(client)
    unlock(client, owner)
    mock_model(monkeypatch)
    events(client.post('/api/v1/code/endless', headers=owner, json={'mode': 'ottly'}))
    assert len(saved_questions()) == 1
    assert client.request('DELETE', '/api/v1/auth/me', headers=owner,
                          json={'current_password': 'TestPass1234!'}).status_code == 200
    assert saved_questions() == []


def test_profile_deduplicates_failures_and_keeps_later_pass_as_evidence(client):
    from app.core.database import get_db
    from app.models.learning_submission import LearningSubmission
    from app.models.user import User
    from app.services.endless import learning_profile
    from main import app
    owner = login(client)
    with next(app.dependency_overrides[get_db]()) as db:
        user_id = db.query(User).filter_by(username='submission_student').one().id
        for passed in [False, False, True]:
            db.add(LearningSubmission(user_id=user_id, problem_id='same-v1', problem_title='累加',
                                     problem_description='任务', code='print(1)', judge_json={}, passed=passed,
                                     knowledge_ids=['K08'], analysis_json={'status': 'ready', 'source': 'ai',
                                     'content': {'misconception_tag': 'accumulation_error'}}))
        db.commit()
        profile = learning_profile(db, user_id)
    assert len(profile['recent_failures']) == 1
    assert profile['recent_failures'][0]['later_passed']


def test_review_must_supply_independent_inputs_and_disagreement_is_rejected():
    from app.services.endless import Candidate, GenerationError, Review, validate_review
    lesson = Candidate.model_validate(draft()).as_lesson()
    with pytest.raises(GenerationError):
        validate_review(lesson, Review.model_validate(review(boundary_cases=[
            {'stdin': '3\n', 'stdout': '6\n'}, {'stdin': '1\n', 'stdout': '1\n'},
        ])))
    with pytest.raises(GenerationError):
        validate_review(lesson, Review.model_validate(review(boundary_cases=[
            {'stdin': '3\n', 'stdout': '999\n'}, {'stdin': '2\n', 'stdout': '3\n'},
        ])))


def test_real_generation_and_review_clients_use_configured_provider_and_validated_json(client, monkeypatch):
    from app.services import error_analysis
    owner = login(client)
    unlock(client, owner)
    monkeypatch.setattr(error_analysis, 'DEEPSEEK_API_KEY', 'endless-test-key')
    monkeypatch.setattr(error_analysis, 'DEEPSEEK_BASE_URL', 'https://deepseek.test')
    factory = httpx.AsyncClient
    calls = []
    def respond(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert str(request.url) == 'https://deepseek.test/chat/completions'
        assert request.headers['Authorization'] == 'Bearer endless-test-key'
        assert payload['response_format'] == {'type': 'json_object'}
        assert payload['thinking']['type'] == 'enabled'
        content = draft() if len(calls) == 1 else review()
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop',
            'message': {'content': json.dumps(content), 'reasoning_content': 'PRIVATE_REASONING'}}]})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: factory(transport=httpx.MockTransport(respond), **kwargs))
    response = client.post('/api/v1/code/endless', headers=owner, json={'mode': 'ottly'})
    assert events(response)[-1]['stage'] == 'ready'
    assert len(calls) == 2 and 'PRIVATE_REASONING' not in response.text
