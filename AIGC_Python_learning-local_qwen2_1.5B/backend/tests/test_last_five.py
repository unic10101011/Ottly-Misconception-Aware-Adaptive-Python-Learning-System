"""New lessons complete the curriculum without reinterpreting legacy records."""
import pytest
from pydantic import ValidationError

from test_greeting import client, account, submit
from app.services.problem_catalog import PROBLEMS, LEVELS, Lesson
from app.services.submission import judge_submission


def test_last_five_learning_flow(client):
    headers = account(client, 'twelve_student')
    assert submit(client, headers, 'level2', 'print(5050)').json()['data']['judge']['passed']
    assert client.get('/api/v1/code/problems/shell-total-v1', headers=headers).status_code == 403
    for slot in LEVELS[:7]:
        lesson = PROBLEMS[slot.problem_id]
        assert submit(client, headers, lesson.problem_id, lesson.reference_solution).json()['data']['judge']['passed']
    for slot in LEVELS[7:]:
        lesson = PROBLEMS[slot.problem_id]
        url = '/api/v1/code/problems/' + slot.problem_id
        if slot.id < 12:
            assert client.get('/api/v1/code/problems/' + LEVELS[slot.id].problem_id, headers=headers).status_code == 403
        data = client.get(url, headers=headers).json()['data']
        assert data['story'] and data['teaching'] and data['examples']
        assert not {'tests', 'function_tests', 'assessment', 'hints', 'reference_solution'} & data.keys()
        assert client.get(url + '/solution', headers=headers).status_code == 403
        run = client.post('/api/v1/code/run', headers=headers, json={
            'code': lesson.reference_solution, 'stdin': lesson.examples[0].stdin,
        }).json()['data']
        assert run['success'] and run['output'] == lesson.examples[0].stdout
        assert not client.get(url, headers=headers).json()['data']['completed']
        failed = submit(client, headers, lesson.problem_id, 'print("incorrect")').json()['data']
        assert not failed['judge']['passed']
        assert failed['analysis']['status'] == 'ready' and failed['analysis']['source'] == 'fixed'
        assert failed['analysis']['content']['knowledge_ids'] == lesson.knowledge_ids
        if slot.id in (11, 12):
            assert failed['judge']['status'] == 'wrong_answer' and failed['error_type'] == 'WRONG_ANSWER'
            assert failed['judge']['cases'][0]['errors'][0]['type'] == 'REQUIREMENT_NOT_MET'
        for level in (1, 2, 3):
            saved = client.patch(f"/api/v1/code/submissions/{failed['submission_id']}/hints",
                                 headers=headers, json={'level': level})
            assert saved.json()['data']['hints_viewed_max'] == level
        review_headers = {**headers, 'X-Review-Source-Id': str(failed['submission_id'])}
        accepted = submit(client, review_headers, lesson.problem_id, lesson.reference_solution).json()['data']
        assert accepted['judge']['passed'] and accepted['analysis']['status'] == 'skipped'
        assert accepted['judge']['total_cases'] == len(lesson.tests) + len(lesson.function_tests)
        for case in accepted['judge']['cases']:
            if case['visibility'] == 'hidden':
                assert case['actual_output'] == case['expected_output'] == '' and case['errors'] == []
        assert client.get(url + '/solution', headers=headers).json()['data']['reference_solution'] == lesson.reference_solution
        history = client.get('/api/v1/code/submissions?problem_id=' + lesson.problem_id, headers=headers).json()['data']
        assert history['total'] == 2
        old = next(row for row in history['items'] if row['id'] == failed['submission_id'])
        assert old['hints_viewed_max'] == 3 and old['resolved_later']
        assert old['knowledge_ids'] == lesson.knowledge_ids and old['difficulty'] == lesson.difficulty
        assert old['version'] == 1 and old['schema_version'] == '1.0.0'
        assert history['items'][0]['review_source_id'] == failed['submission_id']
    token = client.post('/api/v1/auth/login', json={
        'username': 'twelve_student', 'password': 'TestPass1234!',
    }).json()['data']['access_token']
    levels = client.get('/api/v1/code/levels', headers={'Authorization': 'Bearer ' + token}).json()['data']['items']
    assert len(levels) == 12 and all(item['status'] == 'completed' for item in levels)
    other = account(client, 'twelve_other', '13900000002')
    assert client.get('/api/v1/code/problems/count-at-least-v1', headers=other).status_code == 403
    assert client.get('/api/v1/code/problems/count-at-least-v1/solution', headers=other).status_code == 403
    assert client.get('/api/v1/code/submissions', headers=other).json()['data']['total'] == 0


@pytest.mark.parametrize('problem_id,code', [
    ('shell-total-v1', 'n=int(input())\ntotal=0\nfor i in range(1,n+1):\n total=i\nprint(total)'),
    ('shell-total-v1', 'n=int(input())\nfor i in range(1,n+1):\n total=0\n total=total+i\nprint(total)'),
    ('shell-total-v1', 'n=int(input())\ntotal=0\nfor i in range(1,n):\n total+=i\nprint(total)'),
    ('shell-total-v1', 'n=int(input())\ntotal=0\nfor i in range(1,n+1):\n total+=i\n print(total)'),
    ('shell-savings-v1', 'target=int(input());saved=0;days=0\nwhile saved<=target:\n saved+=3\n days+=1\nprint(days)'),
    ('shell-savings-v1', 'target=int(input());saved=0;days=0\nwhile saved<target:\n saved+=3\n days+=1\nprint(saved)'),
    ('shell-savings-v1', 'target=int(input());saved=0;days=0\nwhile saved<target:\n saved+=3\nprint(days)'),
    ('radio-text-v1', 'text=input().strip();target=input().strip()\nprint(len(text));print(text.count(target))'),
    ('radio-text-v1', 'text=input().lower();target=input().lower()\nprint(len(text));print(text.count(target))'),
    ('radio-text-v1', 'text=input();target=input();count=0\nfor char in text:\n count+=1\nprint(len(text));print(count)'),
    ('temperature-max-v1', 'n=int(input());values=[]\nfor i in range(n):\n values.append(int(input()))\nlargest=0\nfor value in values:\n if value>largest:\n  largest=value\nprint(largest)'),
    ('temperature-max-v1', 'n=int(input());values=[]\nfor i in range(n):\n values.append(input())\nlargest=values[0]\nfor value in values:\n if value>largest:\n  largest=value\nprint(largest)'),
    ('temperature-max-v1', 'n=int(input());values=[]\nfor i in range(n):\n values=values.append(int(input()))\nprint(values[0])'),
])
def test_concept_and_boundary_mistakes(problem_id, code):
    assert not judge_submission(PROBLEMS[problem_id], code).passed


@pytest.mark.parametrize('operation', ['max(values)', 'sorted(values)[-1]', 'values.sort()'])
def test_max_and_sort_are_rejected(operation):
    lesson = PROBLEMS['temperature-max-v1']
    code = lesson.reference_solution + '\n' + operation
    result = judge_submission(lesson, code)
    assert not result.passed and result.status == 'wrong_answer'
    assert result.cases[0].errors[0].type == 'RequirementError'


def test_requirements_ignore_comments_and_output_strings():
    lesson = PROBLEMS['temperature-max-v1']
    code = lesson.reference_solution + '\n# max sorted sort\nlabel = "max sorted sort"\n'
    assert judge_submission(lesson, code).passed


@pytest.mark.parametrize('replacement', [
    'return count\n    scores.append(0)',  # unreachable append does not matter; variant below mutates before return
    'scores.sort()\n    return count',
    'scores.append(0)\n    return count',
    'count = n - n + count\n    return count',
    'global running_count\n    try:\n        running_count = running_count + count\n    except:\n        running_count = count\n    return running_count',
])
def test_function_contract_in_same_process(replacement):
    lesson = PROBLEMS['count-at-least-v1']
    code = lesson.reference_solution.replace('return count', replacement)
    result = judge_submission(lesson, code)
    if replacement.startswith('return count\n'):
        assert result.passed  # Unreachable code is not a mutation.
    else:
        assert all(case.passed for case in result.cases[:len(lesson.tests)])
        assert not result.passed and any(not case.passed for case in result.cases[len(lesson.tests):])


@pytest.mark.parametrize('old,new', [
    ('score >= threshold', 'score > threshold'),
    ('return count', 'print(count)'),
    ('    return count', '        return count'),
    ('threshold = int(input())', 'threshold = 60'),
    ('count_at_least(scores, threshold):', 'count_at_least(scores, threshold=60):'),
])
def test_function_boundary_return_and_provided_frame(old, new):
    lesson = PROBLEMS['count-at-least-v1']
    assert not judge_submission(lesson, lesson.reference_solution.replace(old, new)).passed


def test_new_metadata_stays_out_of_model_problem_and_invalid_function_cases_rejected():
    lesson = PROBLEMS['count-at-least-v1']
    assert set(lesson.execution_problem().model_dump()) == {'problem_id','title','description','tests','comparison'}
    data = lesson.model_dump()
    data['function_tests'][0]['case_id'] = data['tests'][0]['case_id']
    with pytest.raises(ValidationError, match='duplicate case_id'):
        Lesson.model_validate(data)
    with pytest.raises(ValidationError, match='requires function tests'):
        Lesson.model_validate({**lesson.model_dump(), 'function_tests': []})


def test_function_execution_has_normal_module_namespace():
    from app.services.sandbox.runner import run_code_process
    code = ('offset = 1\ndef add_offset(value):\n    return value + offset\n'
            'def twice(value):\n    return add_offset(value) * 2\nprint(twice(3))')
    result = run_code_process(code)
    assert result['success'] and result['output'] == '8\n'


@pytest.mark.parametrize('slot', LEVELS[7:])
def test_sample_hardcoding_cannot_complete_new_lesson(slot):
    lesson = PROBLEMS[slot.problem_id]
    code = 'print(' + repr(lesson.examples[0].stdout) + ", end='')"
    assert not judge_submission(lesson, code).passed
