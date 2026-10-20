"""Practice questions are real, gated catalog entries, not extra main levels."""
from collections import Counter
import json

from app.services.problem_catalog import DATA_DIR

from test_greeting import client, account, submit

from app.services.problem_catalog import LEVELS, PROBLEMS
from app.services.submission import judge_submission, public_judge


def test_each_level_has_three_published_practice_questions():
    practice = [problem for problem in PROBLEMS.values() if problem.kind == 'practice']
    assert len(practice) == 36
    assert Counter(problem.level_no for problem in practice) == {level: 3 for level in range(1, 13)}
    assert all(problem.published and problem.practice_focus for problem in practice)
    assert all(problem.problem_id not in {slot.problem_id for slot in LEVELS} for problem in practice)
    for problem in practice:
        assert problem.knowledge_ids == [f'K{problem.level_no:02d}']
        assert problem.prerequisite_problem_ids == ([] if problem.level_no == 1 else
                                                     [LEVELS[problem.level_no - 2].problem_id])
        if problem.level_no > 1:
            assert any(case.visibility == 'hidden' for case in problem.tests)


def test_practice_reference_solutions_and_targeted_wrong_answers():
    practice = [problem for problem in PROBLEMS.values() if problem.kind == 'practice']
    wrong_by_id = {item['problem_id']: item['wrong_solution']
                   for item in json.loads((DATA_DIR / 'practice.json').read_text(encoding='utf-8'))}
    for problem in practice:
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
