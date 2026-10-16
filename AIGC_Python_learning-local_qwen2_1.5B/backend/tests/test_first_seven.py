"""Exercise real lessons, progression, reviewed hints and boundary mistakes."""
import pytest

from test_greeting import client, account, submit
from app.services.problem_catalog import PROBLEMS, LEVELS
from app.services.submission import judge_submission


def test_first_seven_full_flow(client):
    headers = account(client, 'seven_student')
    for slot in LEVELS[:7]:
        lesson = PROBLEMS[slot.problem_id]
        url = '/api/v1/code/problems/' + lesson.problem_id
        if slot.id < 7:
            following = '/api/v1/code/problems/' + LEVELS[slot.id].problem_id
            assert client.get(following, headers=headers).status_code == 403
        data = client.get(url, headers=headers).json()['data']
        assert data['completed'] is False
        assert data['story'] and data['teaching'] and data['examples']
        assert lesson.reference_solution.strip() not in data['starter_code']
        assert not {'tests', 'hints', 'reference_solution'} & data.keys()
        assert client.get(url + '/solution', headers=headers).status_code == 403
        run = client.post('/api/v1/code/run', headers=headers, json={
            'code': lesson.reference_solution, 'stdin': lesson.examples[0].stdin,
        }).json()['data']
        assert run['success'] and run['output'] == lesson.examples[0].stdout
        assert client.get(url, headers=headers).json()['data']['completed'] is False

        failed = submit(client, headers, lesson.problem_id, 'print("incorrect")').json()['data']
        assert failed['judge']['passed'] is False
        assert failed['analysis']['status'] == 'preparing'
        prepared = client.post(f"/api/v1/code/submissions/{failed['submission_id']}/analysis", headers=headers)
        assert prepared.status_code == 200, prepared.text
        failed['analysis'] = prepared.json()['data']['analysis']
        assert failed['analysis']['status'] == 'ready'
        assert failed['analysis']['source'] == 'fixed'
        assert failed['analysis']['model'] is None
        assert failed['analysis']['content']['knowledge_ids'] == lesson.knowledge_ids
        assert failed['analysis']['content']['evidence'][0]['case_id'] in {
            case.case_id for case in lesson.tests if case.visibility == 'public'}
        for case in failed['judge']['cases']:
            if case['visibility'] == 'hidden':
                assert case['actual_output'] == case['expected_output'] == ''
                assert case['errors'] == []
        for level in (1, 2, 3):
            saved = client.patch(f"/api/v1/code/submissions/{failed['submission_id']}/hints",
                                 headers=headers, json={'level': level})
            assert saved.json()['data']['hints_viewed_max'] == level
        accepted = submit(client, headers, lesson.problem_id, lesson.reference_solution).json()['data']
        assert accepted['judge']['passed'] and accepted['judge']['failed_tests'] == []
        assert accepted['analysis']['status'] == 'skipped'
        assert client.get(url + '/solution', headers=headers).json()['data']['reference_solution'] == lesson.reference_solution
        history = client.get('/api/v1/code/submissions?problem_id=' + lesson.problem_id, headers=headers).json()['data']
        assert history['total'] == 2
        old = next(item for item in history['items'] if item['id'] == failed['submission_id'])
        assert old['hints_viewed_max'] == 3 and old['resolved_later']
        assert old['schema_version'] == '1.0.0' and old['difficulty'] == lesson.difficulty
        assert old['knowledge_ids'] == lesson.knowledge_ids and old['version'] == 1

    token = client.post('/api/v1/auth/login', json={
        'username': 'seven_student', 'password': 'TestPass1234!',
    }).json()['data']['access_token']
    renewed = {'Authorization': 'Bearer ' + token}
    levels = client.get('/api/v1/code/levels', headers=renewed).json()['data']['items']
    assert all(item['status'] == 'completed' for item in levels[:7])
    assert levels[7]['status'] == 'current' and not levels[7]['published']
    other = account(client, 'seven_other', '13900000002')
    assert client.get('/api/v1/code/problems/shell-shop-v1', headers=other).status_code == 403
    assert client.get('/api/v1/code/problems/coastal-markers-v1/solution', headers=other).status_code == 403
    assert client.get('/api/v1/code/submissions', headers=other).json()['data']['total'] == 0


@pytest.mark.parametrize('problem_id,code', [
    ('shell-shop-v1', 'p=int(input());q=int(input());b=int(input());print(p+q);print(b-p-q)'),
    ('shell-shop-v1', 'p=input();q=input();b=int(input());print(p*q)'),
    ('shell-shop-v1', 'p=int(input());q=int(input());b=int(input());print(p*q);print(p*q-b)'),
    ('shell-groups-v1', 'n=int(input());k=int(input());print(n/k);print(n%k)'),
    ('shell-groups-v1', 'n=int(input());k=int(input());print(n%k);print(n//k)'),
    ('badge-v1', "s=int(input())\nif s>90:\n print('GOLD')\nelif s>60:\n print('SILVER')\nelse:\n print('TRY_AGAIN')"),
    ('badge-v1', "s=int(input())\nif s>=60:\n print('SILVER')\nelif s>=90:\n print('GOLD')\nelse:\n print('TRY_AGAIN')"),
    ('badge-v1', "s=int(input())\nif s>=90:\n print('GOLD')\nif s>=60:\n print('SILVER')\nelse:\n print('TRY_AGAIN')"),
    ('safe-sailing-v1', "t=int(input());w=int(input());print('YES' if t<=2 or w<=3 else 'NO')"),
    ('safe-sailing-v1', "t=int(input());w=int(input());print('YES' if t<2 and w<3 else 'NO')"),
    ('coastal-markers-v1', 'n=int(input())\nfor i in range(n):\n print(i)'),
    ('coastal-markers-v1', 'n=int(input())\nfor i in range(1,n):\n print(i)'),
    ('coastal-markers-v1', 'n=int(input())\nfor i in range(1,n+1):\n pass\nprint(i)'),
    ('coastal-markers-v1', 'n=int(input())\nfor i in range(1,n+1):\n print(i)\nif n==0:\n print(0)'),
])
def test_boundary_and_concept_mistakes_are_rejected(problem_id, code):
    assert not judge_submission(PROBLEMS[problem_id], code).passed


@pytest.mark.parametrize('problem_id', [slot.problem_id for slot in LEVELS[2:7]])
def test_hardcoding_sample_cannot_complete_lesson(problem_id):
    lesson = PROBLEMS[problem_id]
    sample_code = 'print(' + repr(lesson.examples[0].stdout) + ", end='')"
    result = judge_submission(lesson, sample_code)
    assert result.passed_cases > 0 and not result.passed


def test_fallback_preserves_ready_ai_and_never_uses_hidden_or_uncollected_output():
    from app.services.error_analysis import AnalysisResult
    from app.services.lesson_feedback import with_lesson_hints
    from app.services.submission import public_judge
    lesson = PROBLEMS['shell-shop-v1']
    judge = public_judge(judge_submission(lesson, 'print(0)'))
    ready = AnalysisResult(status='ready', message='existing analysis')
    assert with_lesson_hints(lesson, ready, judge) is ready
    unavailable = AnalysisResult(status='unavailable', message='offline')
    judge.cases = [case for case in judge.cases if case.visibility == 'hidden']
    assert with_lesson_hints(lesson, unavailable, judge) is unavailable
    judge = public_judge(judge_submission(lesson, 'print(0)'))
    for case in judge.cases:
        case.output_available = False
    assert with_lesson_hints(lesson, unavailable, judge) is unavailable
