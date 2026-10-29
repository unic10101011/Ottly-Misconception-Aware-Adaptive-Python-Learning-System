"""Captured core72 failures and nearby valid feedback, never a semantic score."""
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from app.services import error_analysis as analysis
from app.services.hint_quality import replacement_statement
from app.services.problem_catalog import PROBLEMS, TestCase as CatalogTestCase
from app.services.submission import JudgeResult


TRIALS = json.loads((Path(__file__).parent/'data/core72_feedback_regressions.json').read_text(encoding='utf-8'))['trials']
CASES = {case['trial_id']: case for case in TRIALS}
FOLLOWUP = json.loads((Path(__file__).parent/'data/core72_followup_regressions.json').read_text(encoding='utf-8'))['candidates']


def problem_for(case):
    problem = PROBLEMS[case['problem_id']].execution_problem()
    if case['mode'] == 'run':
        problem = problem.model_copy(update={'tests': [CatalogTestCase(case_id='run', stdin=case['stdin'], expected_output='')]})
    return problem


def replay(monkeypatch, key, raw=None, review=None):
    case = CASES[key]
    async def respond(client, messages, schema, *args):
        if 'tag_supported' in schema['properties']:
            return json.dumps(review or {'tag_supported': True, 'issues': []}), 0
        return raw if raw is not None else case['original_raw'], 0
    request = AsyncMock(side_effect=respond)
    monkeypatch.setattr(analysis, 'analysis_configuration_error', lambda: None)
    monkeypatch.setattr(analysis, 'request_diagnosis', request)
    result = asyncio.run(analysis.analyze_failure(problem_for(case), case['code'],
        JudgeResult.model_validate(case['judge']), execution_mode=case['mode']))
    return result, request


@pytest.mark.parametrize('key', ['C28-R1','C54-R1','C54-R2','C54-R3','C01-R2'])
def test_captured_single_line_answers_are_rejected_before_review(monkeypatch, key):
    result, request = replay(monkeypatch, key)
    assert result.status == 'invalid_response' and result.content is None
    assert request.await_count == 1


@pytest.mark.parametrize('key', ['C07-R1','C14-R1','C20-R1','C58-R1','C70-R1','C10-R1','C64-R1'])
def test_existing_code_observations_and_expression_explanations_reach_review(monkeypatch, key):
    # A mock review success only checks local false positives, not AI semantics.
    result, request = replay(monkeypatch, key)
    assert result.status == 'ready' and request.await_count == 2


def test_captured_c43_input_notation_passes_without_rewording(monkeypatch):
    result, request = replay(monkeypatch, 'C43-R1')
    assert result.status == 'ready' and request.await_count == 1
    assert result.guidance.hint == json.loads(CASES['C43-R1']['original_raw'])['hint']


@pytest.mark.parametrize('key', ['C37-R1','C70-R1'])
def test_newly_captured_input_and_undefined_name_phrasing_reach_review(monkeypatch, key):
    result, request = replay(monkeypatch, key, raw=FOLLOWUP[key])
    assert result.status == 'ready'
    assert request.await_count == (1 if key=='C37-R1' else 2)


@pytest.mark.parametrize('text', [
    '改成 n=4', '例如 n=4', '公开样例 n=5', '改成公开样例 n=4',
    '公开样例 n=4；改为 total += number', '公开样例 n=4+1',
    '输入 n=4 后改为 `total = 0`。',
])
def test_numeric_assignments_are_not_blanket_exempted(text):
    assert replacement_statement(text, 'total = 0', public_inputs=['4\n']) is not None


@pytest.mark.parametrize('text', ['例如 total = 0 + i', '应该 total = 0', '改成 total = 0', 'foo_total = 0'])
def test_source_prefix_and_directives_do_not_bypass_diagnosis_guard(text):
    assert replacement_statement(text, 'total = 0', allow_source_observation=True)


def test_c40_duplicate_keys_are_explicitly_rejected_not_silently_overwritten(monkeypatch):
    with pytest.raises(ValueError, match='Duplicate JSON key'):
        analysis.parse_analysis_content(CASES['C40-R1']['original_raw'])
    result, request = replay(monkeypatch, 'C40-R1')
    assert result.status == 'invalid_response' and request.await_count == 1
    schema = request.call_args.args[2]['$defs']['Evidence']
    assert all(set(item['properties']) == {'case_id', 'field', 'quote'} for item in schema['anyOf'])


def test_mismatched_citation_is_still_blocked_after_duplicate_key_fix(monkeypatch):
    candidate = json.loads(CASES['C40-R1']['original_raw'])
    # json.loads reproduces the old parser's overwritten, mismatched tuple.
    result, request = replay(monkeypatch, 'C40-R1', json.dumps(candidate, ensure_ascii=False))
    assert result.status == 'invalid_response' and request.await_count == 1
    candidate['evidence'][0]['case_id'] = 'sample-2'
    result, request = replay(monkeypatch, 'C40-R1', json.dumps(candidate, ensure_ascii=False))
    assert result.status == 'ready' and request.await_count == 2


@pytest.mark.parametrize('key', ['C10-R1','C64-R1'])
def test_generation_and_review_share_category_boundaries_and_can_abstain(monkeypatch, key):
    result, request = replay(monkeypatch, key, review={'tag_supported': False, 'issues': []})
    assert result.status == 'ready' and result.content.misconception_tag == 'other'
    for call in request.call_args_list:
        messages = call.args[1]
        assert '字符串中原样输出变量名不归入此类' in ''.join(m['content'] for m in messages)
        assert '不能仅因列表下标越界' in ''.join(m['content'] for m in messages)


def test_run_domain_constraints_are_available_to_both_generation_and_review(monkeypatch):
    result, request = replay(monkeypatch, 'C24-R1', review={'tag_supported': True, 'issues': [
        {'code': 'unsupported_claim', 'reason': '没有区分越界运行输入与题目合法输入域。'}]})
    assert result.status == 'invalid_response' and request.await_count == 2
    for call in request.call_args_list:
        messages = call.args[1]
        facts = json.JSONDecoder().raw_decode(messages[1]['content'])[0]
        assert facts['execution_mode'] == 'run' and facts['failed_cases'][0]['stdin'] == '17\n0\n'
        assert '越界' in messages[0]['content'] and '约束' in messages[0]['content']


def test_guidance_has_actual_expected_differences_for_c08(monkeypatch):
    result, request = replay(monkeypatch, 'C08-R1')
    assert result.status == 'ready'
    facts = json.loads(request.call_args.args[1][1]['content'])
    assert facts['public_cases'][0]['output_differences']
    assert '实际输出误称为输入' in request.call_args.args[1][0]['content']


@pytest.mark.parametrize('failure', [httpx.ConnectTimeout, httpx.ConnectError])
def test_connection_failure_retries_once_before_any_response(monkeypatch, failure):
    attempts = []
    def handler(request):
        attempts.append(request)
        if len(attempts) == 1:
            raise failure('connect failed', request=request)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]})
    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await analysis.request_diagnosis(client, [{'role': 'user', 'content': '{}'}], {}, 100, 100)
    assert asyncio.run(call()) == ('{}', 0)
    assert len(attempts) == 2


@pytest.mark.parametrize('failure', [httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout, httpx.WriteError])
def test_persistent_connect_failure_is_bounded_and_read_write_failures_not_retried(failure):
    attempts = []
    def handler(request):
        attempts.append(request)
        raise failure('transport failure', request=request)
    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await analysis.request_diagnosis(client, [{'role': 'user', 'content': '{}'}], {}, 100, 100)
    with pytest.raises(failure):
        asyncio.run(call())
    assert len(attempts) == (2 if failure in {httpx.ConnectTimeout, httpx.ConnectError} else 1)


@pytest.mark.parametrize('status', [401,402,429,500,503])
def test_received_http_errors_are_not_retried(status):
    attempts = []
    def handler(request):
        attempts.append(request)
        return httpx.Response(status, json={'error': 'not logged'})
    async def call():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await analysis.request_diagnosis(client, [{'role': 'user', 'content': '{}'}], {}, 100, 100)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(call())
    assert len(attempts) == 1
