import json
from pathlib import Path

import httpx
import pytest

from test_submission import client, login


@pytest.fixture
def anyio_backend():
    return 'asyncio'


def ranked_practice(problem_id, tags, difficulty=1):
    from app.services.problem_catalog import PROBLEMS
    return PROBLEMS['practice-08-1-v1'].model_copy(update={
        'problem_id': problem_id, 'target_misconception_tags': tags, 'difficulty': difficulty,
    })


def test_ranking_uses_knowledge_before_difficulty_then_stable_ids():
    from app.services.practice_recommendation import rank_candidates
    first = ranked_practice('practice-a-v1', ['other'], 2)
    second = ranked_practice('practice-b-v1', ['other'], 2)
    unrelated = ranked_practice('practice-c-v1', ['other'], 1).model_copy(update={'knowledge_ids': ['K07']})
    candidates = [unrelated, second, first]
    result = rank_candidates(candidates, misconception_tag=None, knowledge_ids={'K08'})
    assert result == [first, second, unrelated]
    assert candidates == [unrelated, second, first], 'sorting must not mutate the catalog input'


@pytest.mark.anyio
async def test_unique_best_match_uses_tags_then_difficulty_without_model(monkeypatch):
    from app.services import error_analysis
    from app.services.practice_recommendation import recommend_practice
    async def unexpected_request(*args, **kwargs):
        pytest.fail('unique best candidate must not call the model')
    monkeypatch.setattr(error_analysis, 'request_diagnosis', unexpected_request)
    exact = ranked_practice('practice-exact-v1', ['accumulation_error'])
    harder = ranked_practice('practice-harder-v1', ['accumulation_error'], 2)
    unrelated = ranked_practice('practice-unrelated-v1', ['range_boundary'])
    result = await recommend_practice({}, [unrelated, harder, exact],
        misconception_tag='accumulation_error', knowledge_ids={'K08'}, target_difficulty=1)
    assert result.status == 'ready'
    assert result.recommendation.problem_id == exact.problem_id
    assert result.recommendation.model == ''


@pytest.mark.anyio
@pytest.mark.parametrize('tag', [None, 'other'])
async def test_unknown_cause_uses_difficulty_and_does_not_claim_a_misconception(monkeypatch, tag):
    from app.services import error_analysis
    from app.services.practice_recommendation import recommend_practice
    monkeypatch.setattr(error_analysis, 'analysis_configuration_error', lambda: 'not configured')
    generic = ranked_practice('practice-a-v1', ['other'], 3)
    easier = ranked_practice('practice-b-v1', ['condition_error'], 1)
    result = await recommend_practice({}, [generic, easier],
        misconception_tag=tag, knowledge_ids={'K08'}, target_difficulty=1)
    assert result.status == 'ready'
    assert result.recommendation.problem_id == easier.problem_id
    assert '误区' not in result.recommendation.reason


@pytest.mark.anyio
async def test_model_can_choose_only_from_the_best_tied_group(monkeypatch):
    from app.services import error_analysis
    from app.services.practice_recommendation import recommend_practice
    monkeypatch.setattr(error_analysis, 'analysis_configuration_error', lambda: None)
    first = ranked_practice('practice-a-v1', ['accumulation_error'])
    second = ranked_practice('practice-b-v1', ['accumulation_error'])
    lower = ranked_practice('practice-c-v1', ['range_boundary'])
    async def choose(client, messages, *args):
        facts = json.loads(messages[1]['content'])
        assert [item['problem_id'] for item in facts['candidates']] == [first.problem_id, second.problem_id]
        assert all('source_url' not in item and 'tests' not in item for item in facts['candidates'])
        return json.dumps({'problem_id': second.problem_id, 'reason': '再练习一次总数的更新。'}), 0
    monkeypatch.setattr(error_analysis, 'request_diagnosis', choose)
    result = await recommend_practice({}, [lower, second, first],
        misconception_tag='accumulation_error', knowledge_ids={'K08'})
    assert result.recommendation.problem_id == second.problem_id


@pytest.mark.anyio
@pytest.mark.parametrize('failure', ['configuration', 'http', 'timeout', 'invalid_json', 'outside_tie', 'code'])
async def test_tied_model_failures_return_the_stable_rule_choice(monkeypatch, failure):
    from app.services import error_analysis
    from app.services.practice_recommendation import recommend_practice
    monkeypatch.setattr(error_analysis, 'analysis_configuration_error',
                        lambda: 'missing key' if failure == 'configuration' else None)
    first = ranked_practice('practice-a-v1', ['accumulation_error'])
    second = ranked_practice('practice-b-v1', ['accumulation_error'])
    lower = ranked_practice('practice-c-v1', ['range_boundary'])
    async def unavailable(*args, **kwargs):
        if failure == 'configuration':
            pytest.fail('missing configuration must not call the model')
        request = httpx.Request('POST', 'https://deepseek.test/chat/completions')
        if failure == 'timeout':
            raise httpx.ReadTimeout('timeout', request=request)
        if failure == 'http':
            raise httpx.ConnectError('offline', request=request)
        if failure == 'invalid_json':
            return 'not JSON', 0
        return json.dumps({'problem_id': lower.problem_id if failure == 'outside_tie' else second.problem_id,
                           'reason': '```print(1)```' if failure == 'code' else '练习相关知识。'}), 0
    monkeypatch.setattr(error_analysis, 'request_diagnosis', unavailable)
    result = await recommend_practice({}, [second, lower, first],
        misconception_tag='accumulation_error', knowledge_ids={'K08'})
    assert result.status == 'ready'
    assert result.recommendation.problem_id == first.problem_id
    assert result.recommendation.model == ''


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


@pytest.mark.parametrize('status,source,tag,expected', [
    ('ready', 'ai', 'variable_error', 'variable_error'),
    ('ready', 'ai', 'other', 'other'), ('ready', 'ai', None, None),
    ('ready', 'fixed', 'syntax_error', None), ('timeout', 'ai', None, None),
    ('invalid_response', 'ai', None, None), ('preparing', 'ai', None, None),
])
def test_only_a_saved_ready_ai_tag_is_used_for_recommendation(client, monkeypatch, status, source, tag, expected):
    from main import app
    from app.core.database import get_db
    from app.models.learning_submission import LearningSubmission
    from app.api import coding
    from app.services.practice_recommendation import RecommendationResult
    headers = login(client)
    wrong, accepted = corrected(client, headers)
    database = app.dependency_overrides[get_db]()
    db = next(database)
    try:
        row = db.get(LearningSubmission, wrong['submission_id'])
        row.analysis_json = {'status': status, 'source': source, 'message': '', 'content': {
            'misconception_tag': tag, 'suspected_cause': '目前只能确定输出与要求不同。',
            'knowledge_points': ['输出'], 'knowledge_ids': ['K01', 'K99'],
            'evidence': [{'case_id': 'stdout-1', 'field': 'actual_output', 'quote': 'wrong',
                          'explanation': '公开输出与要求不同。'}],
            'hints': {'level1': '题目要输出什么？', 'level2': '对照输出文字。', 'level3': '逐字核对标点后再运行。'},
        }}
        db.commit()
    finally:
        database.close()
    async def observe(failure, candidates, **kwargs):
        assert kwargs == {'misconception_tag': expected, 'knowledge_ids': {'K01'}, 'target_difficulty': 1}
        assert all(item.kind == 'practice' for item in candidates)
        return RecommendationResult(status='skipped')
    monkeypatch.setattr(coding, 'recommend_practice', observe)
    result = recommendation(client, headers, accepted['submission_id'])
    assert result.status_code == 200, result.text


def test_old_cached_recommendation_remains_readable_without_reselection(client, monkeypatch):
    from main import app
    from app.core.database import get_db
    from app.models.learning_submission import LearningSubmission
    from app.api import coding
    headers = login(client)
    _, accepted = corrected(client, headers)
    cached = {'status': 'ready', 'recommendation': {'problem_id': 'practice-01-2-v1',
              'title': '两行广播', 'reason': '巩固输出。', 'level_no': 1, 'model': 'older-model'}, 'message': ''}
    database = app.dependency_overrides[get_db]()
    db = next(database)
    try:
        row = db.get(LearningSubmission, accepted['submission_id'])
        row.analysis_json = {**row.analysis_json, 'practice_recommendation': cached}
        db.commit()
    finally:
        database.close()
    monkeypatch.setattr(coding, 'recommend_practice', lambda *args, **kwargs: pytest.fail('keep cached choice'))
    assert recommendation(client, headers, accepted['submission_id']).json()['data'] == cached


def test_missing_model_configuration_still_recommends_and_practice_does_not_advance_main(client, monkeypatch):
    from app.services import error_analysis
    from app.services.problem_catalog import PROBLEMS
    monkeypatch.setattr(error_analysis, 'ANALYSIS_PROVIDER', 'deepseek')
    monkeypatch.setattr(error_analysis, 'DEEPSEEK_API_KEY', '')
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: pytest.fail('offline recommendation must use rules'))
    headers = login(client)
    _, accepted = corrected(client, headers)
    data = recommendation(client, headers, accepted['submission_id']).json()['data']
    assert data['status'] == 'ready' and data['recommendation']['model'] == ''
    assert '误区' not in data['recommendation']['reason']
    problem_id = data['recommendation']['problem_id']
    assert client.get('/api/v1/code/problems/' + problem_id, headers=headers).status_code == 200
    progress = client.get('/api/v1/code/levels', headers=headers).json()['data']
    assert not submit(client, headers, problem_id, 'print("wrong")')['practice_recommendation_eligible']
    assert not submit(client, headers, problem_id, PROBLEMS[problem_id].reference_solution)['practice_recommendation_eligible']
    assert client.get('/api/v1/code/levels', headers=headers).json()['data'] == progress
    assert recommendation(client, headers, accepted['submission_id']).json()['data'] == data
    rows = client.get('/api/v1/code/submissions', headers=headers).json()['data']['items']
    assert next(row for row in rows if row['id'] == accepted['submission_id'])['passed']
    # A fresh failure/correction cycle also works with the model configuration absent.
    _, again = corrected(client, headers)
    assert recommendation(client, headers, again['submission_id']).json()['data']['status'] == 'ready'


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
    assert result['recommendation']['problem_id'] == 'practice-01-3-v1'
    assert calls == [], 'one remaining candidate must be recommended directly'


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
    assert data['status'] == 'ready' and data['recommendation']['problem_id'] == 'practice-01-1-v1'
    assert data['recommendation']['model'] == ''
    assert 'PRIVATE_PROVIDER_MESSAGE' not in json.dumps(data)
    assert client.get('/api/v1/code/levels', headers=headers).json()['data']['items'][0]['status'] == 'completed'
    history = client.get('/api/v1/code/submissions', headers=headers).json()['data']['items']
    assert history[0]['passed'] and history[0]['analysis']['status'] == 'skipped'


def test_each_of_the_twelve_main_lessons_can_recommend_after_a_correction(client, monkeypatch, cloud):
    from app.services.problem_catalog import PROBLEMS
    from app.services.practice_recommendation import rank_candidates, practice_rank
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
        previous_calls = len(calls)
        result = recommendation(client, headers, accepted['submission_id']).json()['data']
        assert result['status'] == 'ready', result
        assert result['recommendation']['level_no'] == lesson.level_no
        related = [item for item in PROBLEMS.values() if item.kind == 'practice'
                   and set(item.knowledge_ids).intersection(lesson.knowledge_ids)]
        ranked = rank_candidates(related, misconception_tag=None, knowledge_ids=set(lesson.knowledge_ids))
        best = practice_rank(ranked[0], misconception_tag=None, knowledge_ids=set(lesson.knowledge_ids))[:3]
        tied = [item for item in ranked if practice_rank(item, misconception_tag=None,
                knowledge_ids=set(lesson.knowledge_ids))[:3] == best]
        assert result['recommendation']['problem_id'] == tied[-1].problem_id
        assert len(calls) == previous_calls + int(len(tied) > 1)
        if len(tied) > 1:
            assert [item['problem_id'] for item in calls[-1]['candidates']] == [item.problem_id for item in tied]
