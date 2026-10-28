"""Acceptance evidence stays opt-in, private and independent of student feedback."""
import asyncio
import json

import httpx
import pytest

from app.services import error_analysis as analysis
from app.services.ai_acceptance import acceptance_event, acceptance_record
from app.services.problem_catalog import PROBLEMS
from app.services.submission import judge_submission


def test_acceptance_is_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv('AI_ACCEPTANCE_LOG', raising=False)
    with acceptance_record('example', 'diagnosis'):
        acceptance_event('candidate', content='text')
    assert list(tmp_path.iterdir()) == []


def test_records_append_and_contexts_are_isolated(monkeypatch, tmp_path):
    path = tmp_path / 'audit.jsonl'
    monkeypatch.setenv('AI_ACCEPTANCE_LOG', str(path))

    async def task(name):
        with acceptance_record(name, 'guidance'):
            acceptance_event('first', content=name)
            await asyncio.sleep(0)
            acceptance_event('second', content=name)

    async def run():
        await asyncio.gather(task('one'), task('two'))

    asyncio.run(run())
    acceptance_event('outside', content='must not be recorded')
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    assert len(records) == 2
    assert len({record['record_id'] for record in records}) == 2
    for record in records:
        assert [event['content'] for event in record['events']] == [record['problem_id']] * 2


def test_unwritable_acceptance_log_does_not_break_feedback(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv('AI_ACCEPTANCE_LOG', str(tmp_path / 'missing' / 'audit.jsonl'))
    with acceptance_record('example', 'guidance'):
        acceptance_event('result', status='ready')
    assert 'could not be written' in caplog.text


@pytest.mark.parametrize('kind', ['diagnosis', 'guidance'])
def test_real_pipeline_records_candidate_and_rejection_without_secrets(monkeypatch, tmp_path, kind):
    path = tmp_path / 'audit.jsonl'
    monkeypatch.setenv('AI_ACCEPTANCE_LOG', str(path))
    monkeypatch.setattr(analysis, 'DEEPSEEK_API_KEY', 'SECRET_API_KEY')
    problem = PROBLEMS['coastal-markers-v1' if kind == 'diagnosis' else 'shell-total-v1']
    code = ('n = int(input())\nfor i in range(1, n + 2):\n    print(i)' if kind == 'diagnosis'
            else 'n = int(input())\ntotal = 0\nfor i in range(1, n + 1):\n    total = i\nprint(total)')
    judge = judge_submission(problem, code)

    def respond(request):
        facts = json.JSONDecoder().raw_decode(json.loads(request.content)['messages'][1]['content'])[0]
        if 'candidate' in facts:
            body = {'tag_supported': True, 'issues': [
                {'code': 'unsupported_claim', 'reason': '候选声称了没有提供的运行事实。'}]}
        elif kind == 'guidance':
            body = {'hint': '改成 total += i', 'knowledge_points': ['for 循环与 range'], 'question': None}
        else:
            body = {'code_observation': '范围比要求多一个数。', 'suspected_cause': '循环终点过大，多输出一个数。',
                    'evidence': [{**facts['allowed_evidence'][0], 'explanation': '公开结果多出一个数。'}],
                    'knowledge_points': ['for 循环与 range'], 'misconception_tag': 'other'}
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps(body, ensure_ascii=False), 'reasoning_content': 'SECRET_REASONING'}}]})

    factory = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: factory(transport=httpx.MockTransport(respond), **kwargs))
    result = asyncio.run(analysis.analyze_failure(problem, code, judge))
    assert result.status == 'invalid_response'
    assert result.content is None and result.guidance is None
    raw = path.read_text(encoding='utf-8')
    assert 'SECRET_API_KEY' not in raw and 'SECRET_REASONING' not in raw
    assert 'hidden-' not in raw
    record = json.loads(raw)
    events = record['events']
    assert record['feedback_kind'] == kind
    assert any(event['stage'] == 'provider_response' and event['content'] for event in events)
    assert events[-1] == {'stage': 'result', 'status': 'invalid_response'}
    if kind == 'diagnosis':
        review = next(event for event in events if event['stage'] == 'review_result')
        assert review['issues'][0]['reason'] == '候选声称了没有提供的运行事实。'
    else:
        assert events[-3] == {'stage': 'guidance_rejected_field', 'field': 'hint',
                              'rule': 'replacement_statement', 'match': 'total +='}
        assert events[-2]['reason'] == 'Guidance must not contain replacement statements'
