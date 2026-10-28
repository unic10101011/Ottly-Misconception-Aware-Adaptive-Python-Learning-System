"""Protect valid explanations without accepting invented evidence or replacement answers."""
import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.services import error_analysis as analysis
from app.services.hint_quality import line_reference_errors, quality_issues, replacement_statement
from app.services.problem_catalog import PROBLEMS
from app.services.submission import JudgeResult


FIXTURES = json.loads((Path(__file__).parent / 'data/feedback_validation_regressions.json').read_text(encoding='utf-8'))['cases']
D06, D07 = FIXTURES


@pytest.mark.parametrize('text', [
    '源码第4行存在错误。', '代码中的第4行有错。', '第4行代码引用了变量。',
    '代码第4行输出不对。', '源码第0行有错。',
])
def test_nonexistent_explicit_source_lines_are_rejected(text):
    assert line_reference_errors(text, 3, 4, 3)[0]['kind'] == 'source'


@pytest.mark.parametrize('text', [
    '形成第 4 行错误输出。', '实际输出第4行是4。', '输出结果的第4行多余。',
    '第4行输出与题意不符。', '第4行与预期不符。', '检查第99行的含义。',
    '预期输出第4行不存在。', '源码第99行不存在，不应引用它。',
])
def test_output_locations_and_ambiguous_locations_are_not_source_lines(text):
    assert line_reference_errors(text, 3, 4, 3) == []


@pytest.mark.parametrize('text,kind', [
    ('实际输出第5行是5。', 'actual_output'), ('预期输出第4行是4。', 'expected_output'),
    ('第5行输出有误。', 'output'), ('输出第0行有误。', 'output'),
])
def test_output_line_claims_are_checked_against_observed_outputs(text, kind):
    assert line_reference_errors(text, 3, 4, 3)[0]['kind'] == kind


def test_ambiguous_line_is_left_to_semantic_review_without_suppressing_explicit_errors():
    errors = line_reference_errors('第99行需要检查；实际输出第4行多余，但代码第8行有错。', 3, 4, 3)
    assert [(item['kind'], item['line']) for item in errors] == [('source', 8)]


@pytest.mark.parametrize('text', ['源码第2行不存在。', '实际输出第4行不存在。'])
def test_false_claims_that_existing_lines_are_absent_are_rejected(text):
    assert line_reference_errors(text, 3, 4, 3)


@pytest.mark.parametrize('text', [
    '观察原代码 `total = i`，想一想是否保留旧值。',
    '原代码“total=i”每轮如何更新变量？',
    '对照「total = i」与前两轮结果。',
    '`print("a b")` 是你当前写的输出语句。',
    '`for i in range(1, n + 1):` 是当前循环的范围。',
    '`return count` 是你当前的返回语句。',
    '概念上赋值号 = 和比较符号 == 有什么区别？',
    '思考 `print()` 的返回值是什么。',
])
def test_observational_quotes_and_concept_references_are_allowed(text):
    code = 'total = i\nprint("a b")\nfor i in range(1, n + 1):\n    return count'
    assert replacement_statement(text, code) is None


@pytest.mark.parametrize('text', [
    '改成 total += i', '例如 `total = total + i`。', '把它改为 `total = i`。',
    '替换成下面的：`total = i`', '改成 print(1)', '改为 `print()` 的调用。',
    '应该 `total = i`。', '请用 `total = i`。',
    '请用 `return count`。', '改成 return count', '改成 total = sum(range(5))',
    '当前代码 `print("ab")`。',
])
def test_replacement_statements_and_modified_literals_remain_blocked(text):
    # return count is not in this student's code; a new statement must not be exempt.
    assert replacement_statement(text, 'total = i\nprint("a b")') is not None


def draft_content(candidate=None):
    judge = JudgeResult.model_validate(D06['judge'])
    draft = analysis.parse_analysis_content(json.dumps(candidate or D06['candidate'], ensure_ascii=False))
    return analysis.AnalysisContent(**draft.model_dump(exclude={'code_observation'}),
                                    hints=analysis.safe_hints(PROBLEMS[D06['problem_id']], judge))


def test_captured_d06_candidate_passes_local_checks_without_rewording():
    judge = JudgeResult.model_validate(D06['judge'])
    content = draft_content()
    analysis.validate_grounding(content, judge, problem_id=D06['problem_id'], code=D06['code'])
    assert quality_issues(content.model_dump(), D06['code'], [], public_cases=D06['judge']['cases']) == []


def test_diagnosis_can_observe_original_statement_near_a_location_discussion():
    content = draft_content()
    content.suspected_cause = '修改第3行前，先观察原代码 `print(i)` 的输出次数。'
    analysis.validate_grounding(content, JudgeResult.model_validate(D06['judge']),
                                problem_id=D06['problem_id'], code=D06['code'])


def test_evidence_line_check_uses_its_case_and_ignores_hidden_cases():
    content = draft_content().model_dump()
    content['evidence'] = [{'case_id': 'sample-2', 'explanation': '实际输出第2行是2。'}]
    hidden = {'case_id': 'hidden-1', 'visibility': 'hidden', 'actual_output': '1\n' * 99, 'expected_output': '1\n' * 99}
    details = []
    issues = quality_issues(content, D06['code'], [], public_cases=[*D06['judge']['cases'], hidden], details=details)
    assert issues == ['unsupported_claim']
    assert details[0]['field'] == 'evidence.0.explanation'
    assert details[0]['available_lines'] == 1


async def replay(monkeypatch, case, candidate, review=None):
    async def respond(client, messages, schema, *args):
        if 'tag_supported' in schema['properties']:
            return json.dumps(review or {'tag_supported': True, 'issues': []}), 0
        return json.dumps(candidate, ensure_ascii=False), 0

    monkeypatch.setattr(analysis, 'analysis_configuration_error', lambda: None)
    request = AsyncMock(side_effect=respond)
    monkeypatch.setattr(analysis, 'request_diagnosis', request)
    result = await analysis.analyze_failure(PROBLEMS[case['problem_id']], case['code'], JudgeResult.model_validate(case['judge']))
    return result, request


def test_d06_reaches_semantic_review_and_its_rejection_still_counts(monkeypatch):
    result, request = asyncio.run(replay(monkeypatch, D06, D06['candidate']))
    assert result.status == 'ready' and request.await_count == 2
    review = {'tag_supported': True, 'issues': [{'code': 'unsupported_claim', 'reason': '真实事实矛盾仍须拦截。'}]}
    result, request = asyncio.run(replay(monkeypatch, D06, D06['candidate'], review))
    assert result.status == 'invalid_response' and request.await_count == 2


@pytest.mark.parametrize('field', ['hint', 'prompt', 'option', 'explanation'])
def test_every_guidance_field_rejects_direct_fixes_and_records_its_location(monkeypatch, tmp_path, field):
    path = tmp_path / 'acceptance.jsonl'
    monkeypatch.setenv('AI_ACCEPTANCE_LOG', str(path))
    candidate = copy.deepcopy(D07['candidate'])
    candidate['question']['explanation'] = '每轮保留之前已经累计的值。'
    if field == 'hint':
        candidate['hint'] = '改为 total += i'
        expected = 'hint'
    elif field == 'option':
        candidate['question']['options'][0] = '改为 total += i'
        expected = 'question.options.0'
    else:
        candidate['question'][field] = '改为 total += i'
        expected = 'question.' + field
    result, request = asyncio.run(replay(monkeypatch, D07, candidate))
    assert result.status == 'invalid_response' and result.guidance is None
    assert request.await_count == 1  # Never retry or discard an invalid quiz silently.
    events = json.loads(path.read_text(encoding='utf-8'))['events']
    blocked = next(event for event in events if event['stage'] == 'guidance_rejected_field')
    assert blocked['field'] == expected and blocked['rule'] == 'replacement_statement'


def test_d07_captured_fix_is_blocked_but_concept_only_explanation_passes(monkeypatch):
    result, _ = asyncio.run(replay(monkeypatch, D07, D07['candidate']))
    assert result.status == 'invalid_response'
    candidate = copy.deepcopy(D07['candidate'])
    candidate['question']['explanation'] = candidate['question']['explanation'].replace('（如 total = total + i）', '')
    candidate['hint'] = '观察你写的 `total = i`，每轮是否保留之前的和？'
    result, request = asyncio.run(replay(monkeypatch, D07, candidate))
    assert result.status == 'ready' and request.await_count == 1
    messages, schema = request.call_args.args[1:3]
    prompt = messages[0]['content']
    assert all(name in prompt for name in ('hint', 'question.prompt', 'question.options', 'question.explanation'))
    assert '作答后解释也不例外' in prompt
    assert '直接修正语句' in schema['$defs']['GuidanceQuestion']['properties']['explanation']['description']


@pytest.mark.parametrize('hint', ['源码第99行有错。', '实际输出第99行有错。', '隐藏测试输入为99。'])
def test_guidance_still_rejects_invented_locations_and_private_evidence(monkeypatch, hint):
    candidate = copy.deepcopy(D07['candidate'])
    candidate['question'] = None
    candidate['hint'] = hint
    result, _ = asyncio.run(replay(monkeypatch, D07, candidate))
    assert result.status == 'invalid_response'


def test_fabricated_evidence_quote_is_still_rejected_before_review(monkeypatch):
    candidate = copy.deepcopy(D06['candidate'])
    candidate['evidence'][0]['quote'] = 'fabricated_output'
    result, request = asyncio.run(replay(monkeypatch, D06, candidate))
    assert result.status == 'invalid_response' and request.await_count == 1
