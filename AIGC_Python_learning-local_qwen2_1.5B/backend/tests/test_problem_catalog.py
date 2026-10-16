import json

import pytest
from pydantic import ValidationError

from app.services.problem_catalog import PROBLEMS, KNOWLEDGE, LEVELS, Lesson, validate_catalog, load_catalog, DATA_DIR


@pytest.mark.parametrize('changes', [
    {'difficulty':4}, {'difficulty':True}, {'version':2}, {'schema_version':'2.0.0'},
    {'problem_id':'Invalid ID'}, {'knowledge_ids':['K02','K02']},
    {'tests':[]}, {'tests':[PROBLEMS['greeting-v1'].tests[0].model_dump()]},
    {'comparison':'legacy_trim'},
])
def test_invalid_lesson_is_rejected(changes):
    data = PROBLEMS['greeting-v1'].model_dump()
    data.update(changes)
    with pytest.raises(ValidationError):
        Lesson.model_validate(data)


@pytest.mark.parametrize('changes', [
    {'knowledge_ids':['K99']}, {'prerequisite_knowledge_ids':['K99']},
    {'prerequisite_problem_ids':['missing-v1']},
    {'prerequisite_problem_ids':['greeting-v1']},
])
def test_unknown_and_self_references_rejected(changes):
    problems = {**PROBLEMS, 'greeting-v1':PROBLEMS['greeting-v1'].model_copy(update=changes)}
    with pytest.raises(ValueError):
        validate_catalog(problems, KNOWLEDGE, LEVELS)


def test_cyclic_prerequisites_and_ambiguous_aliases_rejected():
    problems = {**PROBLEMS, 'level1':PROBLEMS['level1'].model_copy(update={'prerequisite_problem_ids':['greeting-v1']})}
    with pytest.raises(ValueError, match='cyclic'):
        validate_catalog(problems, KNOWLEDGE, LEVELS)
    knowledge = {**KNOWLEDGE, 'K01':KNOWLEDGE['K01'].model_copy(update={'aliases':['变量']})}
    with pytest.raises(ValueError, match='ambiguous'):
        validate_catalog(PROBLEMS, knowledge, LEVELS)


def test_duplicate_case_and_problem_ids_are_rejected(tmp_path):
    data = PROBLEMS['greeting-v1'].model_dump()
    data['tests'][1]['case_id'] = data['tests'][0]['case_id']
    with pytest.raises(ValidationError, match='duplicate case_id'):
        Lesson.model_validate(data)
    for path in DATA_DIR.glob('*.json'):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    (tmp_path / 'duplicate.json').write_text(json.dumps(PROBLEMS['greeting-v1'].model_dump()), encoding='utf-8')
    with pytest.raises(ValueError, match='duplicate problem ID'):
        load_catalog(tmp_path)


def test_all_reference_solutions_pass_real_tests():
    from app.services.submission import judge_submission
    for problem in PROBLEMS.values():
        assert judge_submission(problem, problem.reference_solution).passed, problem.problem_id


@pytest.mark.parametrize('raw,expected', [
    ('语法错误','SYNTAX_ERROR'), ('IndentationError','INDENTATION_ERROR'),
    ('NameError','NAME_ERROR'), ('TypeError','TYPE_ERROR'), ('ValueError','VALUE_ERROR'),
    ('ZeroDivisionError','ZERO_DIVISION_ERROR'), ('IndexError','INDEX_ERROR'), ('KeyError','KEY_ERROR'),
    ('AttributeError','ATTRIBUTE_ERROR'), ('EOFError','EOF_ERROR'), ('ImportError','IMPORT_ERROR'),
    ('安全警告','SECURITY_ERROR'), ('OutputLimitError','OUTPUT_LIMIT_EXCEEDED'),
    ('超时警告','TIMEOUT'), ('UnknownError','RUNTIME_ERROR'), ('NAME_ERROR','NAME_ERROR'),
])
def test_stable_error_codes(raw, expected):
    from app.services.learning_contract import error_code
    assert error_code(raw) == expected


def test_aggregate_timeout_takes_priority_and_failed_tests_are_always_derived():
    from app.services.submission import CaseResult, ExecutionError, JudgeResult
    from app.services.learning_contract import contract_judge, submission_error
    def case(case_id, error):
        return CaseResult(case_id=case_id, passed=False, expected_output='', actual_output='',
                          errors=[ExecutionError(type=error, message='error')], execution_time=0)
    judge = JudgeResult(status='timeout', passed=False, passed_cases=0, total_cases=2,
                        cases=[case('first','NameError'), case('second','超时警告')])
    assert submission_error(judge) == 'TIMEOUT'
    stored = judge.model_dump()
    stored['failed_tests'] = ['invented']
    assert contract_judge(stored).failed_tests == ['first','second']


@pytest.mark.parametrize('code,expected', [
    ('if True:\nprint(1)', 'INDENTATION_ERROR'),
    ('for i in range(3)\n    print(i)', 'SYNTAX_ERROR'),
    ('print(missing_name)', 'NAME_ERROR'),
    ('print(input())', 'EOF_ERROR'),
])
def test_real_execution_codes_are_normalized_without_mutating_model_evidence(code, expected):
    from app.services.submission import judge_submission
    from app.services.learning_contract import contract_judge, submission_error
    raw = judge_submission(PROBLEMS['level1'], code)
    before = raw.model_dump()
    assert submission_error(raw, code=code) == expected
    assert contract_judge(raw, code=code).cases[0].errors[0].type == expected
    assert raw.model_dump() == before
