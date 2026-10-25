"""Practice questions are real, gated catalog entries, not extra main levels."""
from collections import Counter
import json
import pytest

from app.services.problem_catalog import DATA_DIR

from test_greeting import client, account, submit

from app.services.problem_catalog import LEVELS, PROBLEMS
from app.services.submission import judge_submission, public_judge


def test_all_practice_questions_have_recommendation_metadata():
    allowed = {'range_boundary', 'accumulation_error', 'condition_error',
               'variable_error', 'syntax_error', 'other'}
    practice = [item for item in PROBLEMS.values() if item.kind == 'practice']
    assert len(practice) == 45
    for item in practice:
        assert type(item.difficulty) is int and item.difficulty in {1, 2, 3}, item.problem_id
        assert 1 <= len(item.target_misconception_tags) <= 2, item.problem_id
        assert set(item.target_misconception_tags) <= allowed, item.problem_id
        assert item.source_url and item.source_url.startswith('https://'), item.problem_id


@pytest.mark.parametrize('changes', [
    {'difficulty': None}, {'difficulty': True}, {'difficulty': 4},
    {'target_misconception_tags': []}, {'target_misconception_tags': ['invented']},
    {'target_misconception_tags': ['other', 'other']}, {'source_url': None},
])
def test_offline_metadata_errors_name_the_problem(changes):
    from verify_practice_content import validate_metadata
    spec = json.loads((DATA_DIR / 'practice.json').read_text(encoding='utf-8'))[0]
    spec.update(changes)
    with pytest.raises(AssertionError, match=spec['problem_id']):
        validate_metadata(spec)


@pytest.mark.parametrize('changes', [
    {'target_misconception_tags': []}, {'target_misconception_tags': ['invented']},
    {'target_misconception_tags': ['variable_error', 'variable_error']},
    {'target_misconception_tags': ['variable_error', 'condition_error', 'other']},
    {'source_url': None}, {'source_url': 'http://example.com'}, {'difficulty': True},
])
def test_invalid_practice_recommendation_metadata_is_rejected(changes):
    from pydantic import ValidationError
    from app.services.problem_catalog import Lesson
    data = PROBLEMS['practice-03-4-v1'].model_dump()
    data.update(changes)
    with pytest.raises(ValidationError):
        Lesson.model_validate(data)


@pytest.mark.parametrize('filename', ['practice.json', 'practice-03-4-v1.json'])
def test_catalog_errors_identify_the_practice_with_unknown_tags(tmp_path, filename):
    from app.services.problem_catalog import load_catalog
    for path in DATA_DIR.glob('*.json'):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    path = tmp_path / filename
    data = json.loads(path.read_text(encoding='utf-8'))
    item = data[0] if isinstance(data, list) else data
    item['target_misconception_tags'] = ['invented']
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match=item['problem_id']):
        load_catalog(tmp_path)


def test_each_level_has_expected_published_practice_questions():
    practice = [problem for problem in PROBLEMS.values() if problem.kind == 'practice']
    assert len(practice) == 45
    assert Counter(problem.level_no for problem in practice) == {
        level: 6 if level in (3, 4, 5) else 3 for level in range(1, 13)
    }
    assert all(problem.published and problem.practice_focus for problem in practice)
    assert all(problem.problem_id not in {slot.problem_id for slot in LEVELS} for problem in practice)
    for problem in practice:
        assert problem.knowledge_ids == [f'K{problem.level_no:02d}']
        assert problem.prerequisite_problem_ids == ([] if problem.level_no == 1 else
                                                     [LEVELS[problem.level_no - 2].problem_id])
        if problem.level_no > 1:
            assert any(case.visibility == 'hidden' for case in problem.tests)


@pytest.mark.parametrize('problem_id', [
    problem.problem_id for problem in PROBLEMS.values() if problem.kind == 'practice'
])
def test_practice_reference_solutions_and_targeted_wrong_answers(problem_id):
    problem = PROBLEMS[problem_id]
    wrong_by_id = {item['problem_id']: item['wrong_solution']
                   for item in json.loads((DATA_DIR / 'practice.json').read_text(encoding='utf-8'))}
    from verify_practice_content import FULL_PRACTICE_MISTAKES
    wrong_by_id.update({
        problem_id: PROBLEMS[problem_id].reference_solution.replace(before, after, 1)
        for problem_id, (before, after) in FULL_PRACTICE_MISTAKES.items()
    })
    assert judge_submission(problem, problem.reference_solution).passed, problem.problem_id
    assert not judge_submission(problem, wrong_by_id[problem.problem_id]).passed, problem.problem_id


def test_function_practice_checks_return_type_not_only_printed_text():
    problem = PROBLEMS['practice-12-2-v1']
    wrong = problem.reference_solution.replace(
        'return wind <= 5 and wave <= 2',
        "return 'True' if wind <= 5 and wave <= 2 else 'False'",
    )
    judged = judge_submission(problem, wrong)
    assert not judged.passed
    hidden = next(case for case in public_judge(judged).cases if case.case_id == 'hidden-function-1')
    assert hidden.expected_output == hidden.actual_output == ''
    assert hidden.errors == [] and not hidden.output_available


def test_function_practice_cannot_replace_judge_print():
    problem = PROBLEMS['practice-12-2-v1']
    wrong = problem.reference_solution.replace(
        'return wind <= 5 and wave <= 2',
        "global print\n    original_print = print\n"
        "    def fake_print(value):\n"
        "        original_print(value if type(value) is str else True)\n"
        "    print = fake_print\n"
        "    return 'True' if wind <= 5 and wave <= 2 else 'False'",
    )
    assert not judge_submission(problem, wrong).passed


def test_list_maximum_practice_requires_list_traversal():
    problem = PROBLEMS['practice-11-1-v1']
    shortcut = 'n = int(input())\nvalues = []\nfor i in range(n):\n    values.append(int(input()))\nprint(max(values))\n'
    assert not judge_submission(problem, shortcut).passed


def test_practice_is_listed_accessibly_and_does_not_unlock_main_levels(client):
    headers = account(client, 'practice_student', '13900000136')
    listing = client.get('/api/v1/code/practice?level_no=1', headers=headers)
    assert listing.status_code == 200
    items = listing.json()['data']['items']
    assert len(items) == 3
    assert all(item['kind'] == 'practice' and item['available'] for item in items)
    locked = client.get('/api/v1/code/practice?level_no=2', headers=headers).json()['data']['items']
    assert len(locked) == 3 and all(not item['available'] for item in locked)
    assert client.get('/api/v1/code/problems/' + locked[0]['problem_id'], headers=headers).status_code == 403

    problem = PROBLEMS[items[0]['problem_id']]
    detail = client.get('/api/v1/code/problems/' + problem.problem_id, headers=headers).json()['data']
    assert detail['kind'] == 'practice' and detail['practice_focus'] == problem.practice_focus
    assert not {'tests', 'wrong_solution', 'reference_solution', 'hints'} & detail.keys()
    accepted = submit(client, headers, problem.problem_id, problem.reference_solution)
    assert accepted.json()['data']['judge']['passed']
    assert client.get('/api/v1/code/levels', headers=headers).json()['data']['items'][1]['status'] == 'locked'
    assert client.get('/api/v1/code/problems/' + problem.problem_id + '/solution', headers=headers).status_code == 200
