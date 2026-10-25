"""Practice questions are real, gated catalog entries, not extra main levels."""
from collections import Counter
import json
import pytest

from app.services.problem_catalog import DATA_DIR

from test_greeting import client, account, submit

from app.services.problem_catalog import LEVELS, PROBLEMS
from app.services.submission import judge_submission, public_judge


def test_each_level_has_expected_published_practice_questions():
    practice = [problem for problem in PROBLEMS.values() if problem.kind == 'practice']
    assert len(practice) == 66
    assert Counter(problem.level_no for problem in practice) == {
        level: 6 if level >= 3 else 3 for level in range(1, 13)
    }
    assert all(problem.published and problem.practice_focus for problem in practice)
    assert all(problem.problem_id not in {slot.problem_id for slot in LEVELS} for problem in practice)
    for problem in practice:
        assert f'K{problem.level_no:02d}' in problem.knowledge_ids
        assert problem.prerequisite_problem_ids == ([] if problem.level_no == 1 else
                                                     [LEVELS[problem.level_no - 2].problem_id])
        if problem.level_no > 1:
            assert any(case.visibility == 'hidden' for case in problem.tests)


def test_original_practice_has_distinct_stories_and_boundary_cases():
    specs = json.loads((DATA_DIR / 'practice.json').read_text(encoding='utf-8'))
    for spec in specs:
        lesson = PROBLEMS[spec['problem_id']]
        assert lesson.story == spec['story'] and lesson.story != lesson.description
        assert len(lesson.story) >= 40
        if lesson.level_no == 1:
            assert len(lesson.tests) == 1  # Fixed output has only one meaningful input.
        else:
            assert len(lesson.tests) >= 6
            assert len({case.stdin for case in lesson.tests}) == len(lesson.tests)


@pytest.mark.parametrize('problem_id', [
    problem.problem_id for problem in PROBLEMS.values() if problem.kind == 'practice'
])
def test_practice_reference_solutions_and_targeted_wrong_answers(problem_id):
    problem = PROBLEMS[problem_id]
    wrong_by_id = {item['problem_id']: item['wrong_solution']
                   for item in json.loads((DATA_DIR / 'practice.json').read_text(encoding='utf-8'))}
    mistakes = {
        'practice-03-4-v1': ('(length + width) * 2', 'length + width * 2'),
        'practice-03-5-v1': ('before - given', 'given - before'),
        'practice-03-6-v1': ('per_group * groups', 'children + teachers * groups'),
        'practice-04-4-v1': ('remaining // 60', 'total_seconds // 60'),
        'practice-04-5-v1': ('number // 10 % 10', 'number // 10'),
        'practice-04-6-v1': ('(number - 1) % seats_per_row + 1', 'number % seats_per_row'),
        'practice-05-4-v1': ('ottly_count > friend_count', 'ottly_count >= friend_count'),
        'practice-05-5-v1': ('height <= 100', 'height < 100'),
        'practice-05-6-v1': ('print(current - target)', 'print(target - current)'),
        'practice-06-4-v1': ('hour < 18', 'hour <= 18'),
        'practice-06-5-v1': ('left == 1 and right == 0', 'left == 1'),
        'practice-06-6-v1': ('and not sale == 1', ''),
        'practice-07-4-v1': ('range(n, -1, -1)', 'range(n, 0, -1)'),
        'practice-07-5-v1': ('first + i * step', 'first + (i + 1) * step'),
        'practice-07-6-v1': ('weight > 0 and weight <= limit', 'weight <= limit'),
        'practice-08-4-v1': ('expense = expense - change', 'expense = expense + change'),
        'practice-08-5-v1': ('10 + (distance - 5) * 3', 'distance * 3'),
        'practice-08-6-v1': ('    else:\n        streak = 0', '    else:\n        total = 0'),
        'practice-09-4-v1': ('count = 0', 'count = 1'),
        'practice-09-5-v1': ('print(a)', 'print(b)'),
        'practice-09-6-v1': ('while n != 1:', 'while n > 2:'),
        'practice-10-4-v1': ('char != "#"', 'char != "#" and char != " "'),
        'practice-10-5-v1': ('    previous = char', '    previous = ""'),
        'practice-10-6-v1': ('backward = char + backward', 'backward = backward + char'),
        'practice-11-4-v1': ('range(n - 1, -1, -1)', 'range(n - 1, 0, -1)'),
        'practice-11-5-v1': ('values[i] - values[i - 1]', 'values[i - 1] - values[i]'),
        'practice-11-6-v1': ('(i + k) % n', '(i - k) % n'),
        'practice-12-4-v1': ('return low', 'return high'),
        'practice-12-5-v1': ('return longest', 'return current'),
        'practice-12-6-v1': ('values[i] <= values[i - 1]', 'values[i] < values[i - 1]'),
    }
    wrong_by_id.update({
        problem_id: PROBLEMS[problem_id].reference_solution.replace(before, after, 1)
        for problem_id, (before, after) in mistakes.items()
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
