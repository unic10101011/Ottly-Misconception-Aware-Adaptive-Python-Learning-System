"""Check human-labeled examples against the real deterministic judge."""

import pytest

from app.services.problem_catalog import PROBLEMS
from app.services.submission import judge_submission
from personalized_hint_eval_cases import CASES


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
def test_gold_example_has_expected_public_execution(case):
    judge = judge_submission(PROBLEMS['level2'].execution_problem(), case['code'])
    public = judge.cases[0]

    assert public.actual_output == case['output']
    if case['tag'] is None:
        assert judge.status == 'accepted'
    elif case.get('error'):
        assert judge.status == 'execution_error'
        assert any(error.type == case['error'] for error in public.errors)
    else:
        assert judge.status == 'wrong_answer'
        assert public.errors == []
