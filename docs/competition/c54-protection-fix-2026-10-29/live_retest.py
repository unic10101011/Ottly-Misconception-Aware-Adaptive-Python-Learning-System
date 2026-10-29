"""One bounded real-AI replay per planned trial; retain every failed attempt."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import httpx

ROOT = Path('/workspace')
sys.path.insert(0, str(ROOT/'backend'))
from app.services import error_analysis as analysis
from app.services.problem_catalog import PROBLEMS, TestCase
from app.services.submission import JudgeResult

OUT = Path('/evidence')


def now():
    return datetime.now(timezone.utc).isoformat()


def save(name, data):
    (OUT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


async def main():
    assert not (OUT/'real-ai-results.json').exists(), 'Never overwrite or silently rerun evidence.'
    assert not analysis.analysis_configuration_error(), 'AI is not configured.'
    assert analysis.DEEPSEEK_BASE_URL == 'https://api.deepseek.com', 'Unexpected provider URL.'
    source = ROOT/'docs/competition/c54-protection-fix-2026-10-29/replay-fixtures.json'
    fixtures = json.loads(source.read_text(encoding='utf-8'))['trials']
    plan = json.loads((ROOT/'docs/competition/c54-protection-fix-2026-10-29/retest-plan.json').read_text(encoding='utf-8'))
    assert [c['trial_id'] for c in fixtures] == plan['trial_ids']
    report = {'started_at': now(), 'finished_at': None, 'scope': plan['policy'], 'real_ai': True,
              'fixture_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'human_review': 'pending', 'trials': []}
    save('real-ai-results.json', report)
    active = None
    calls = []
    pending = []

    def append_call(record):
        calls.append(record)
        with (OUT/'provider-calls.jsonl').open('a', encoding='utf-8') as target:
            target.write(json.dumps(record, ensure_ascii=False)+'\n')

    async def on_request(request):
        record = {'call_id': len(calls)+len(pending)+1, 'trial_id': active, 'started_at': now(),
                  'request': json.loads(request.content), 'http_status': None, 'response': None,
                  'transport_error': None, '_started': time.monotonic()}
        pending.append(record)

    async def on_response(response):
        await response.aread()
        record = pending.pop()
        record['http_status'] = response.status_code
        try:
            body = response.json()
            record['response'] = {key: body.get(key) for key in ('id','model','created','usage')}
            record['response']['choices'] = [
                {'finish_reason': c.get('finish_reason'), 'message': {'content': c.get('message',{}).get('content')}}
                for c in body.get('choices', [])]
        except (ValueError, AttributeError, TypeError):
            record['response_parse_error'] = True
        record['seconds'] = round(time.monotonic()-record.pop('_started'), 3)
        record['finished_at'] = now()
        append_call(record)

    factory = httpx.AsyncClient
    analysis.httpx.AsyncClient = lambda **kwargs: factory(event_hooks={'request':[on_request], 'response':[on_response]}, **kwargs)
    original_request = analysis.request_diagnosis

    async def recorded_request(*args, **kwargs):
        error_name = None
        try:
            return await original_request(*args, **kwargs)
        except Exception as error:
            error_name = type(error).__name__
            raise
        finally:
            while pending:
                record = pending.pop(0)
                record['transport_error'] = error_name or 'connection_failure_before_successful_retry'
                record['seconds'] = round(time.monotonic()-record.pop('_started'), 3)
                record['finished_at'] = now()
                append_call(record)
    analysis.request_diagnosis = recorded_request
    captured = json.loads((ROOT/'backend/tests/data/c54_answer_protection_regressions.json').read_text(encoding='utf-8'))
    by_id = {case['trial_id']:case for case in fixtures}
    gates = []
    save('review-gate-results.json', {'status':'running','items':gates})
    for spec in plan['review_gate_plan']:
        active = spec['id']
        if spec['source']=='dev12-D06':
            case = json.loads((ROOT/'backend/tests/data/feedback_validation_regressions.json').read_text(encoding='utf-8'))['cases'][0]
            raw = json.dumps(case['candidate'],ensure_ascii=False)
        else:
            case = by_id['C54-R3' if spec['source']=='rejected_raw' else spec['source']]
            raw = captured['rejected_raw'] if spec['source']=='rejected_raw' else captured['allowed_raw'][spec['source']]
        draft = analysis.parse_analysis_content(raw)
        if spec.get('cause'):
            draft.suspected_cause = spec['cause']
        problem = PROBLEMS[case['problem_id']].execution_problem()
        if case.get('mode')=='run':
            problem = problem.model_copy(update={'tests':[TestCase(case_id='run',stdin=case['stdin'],expected_output='')]})
        judge = JudgeResult.model_validate(case['judge'])
        inputs = {c.case_id:c.stdin for c in problem.tests if c.visibility=='public'}
        facts = {'execution_mode':case.get('mode','submit'),'judge_status':judge.status,
                 'diagnosis_scope':analysis.diagnosis_scope(problem,judge),
                 'problem':problem.model_dump(exclude={'tests'}),'student_code':case['code'],'related_history':[],
                 'failed_cases':[{'case_id':c.case_id,'stdin':inputs.get(c.case_id,''),
                     'actual_output':c.actual_output[:1000],'expected_output':c.expected_output[:1000],
                     'output_available':c.output_available,'errors':[e.model_dump() for e in c.errors],
                     'output_differences':analysis.output_differences(problem,c),'output_lines':analysis.output_lines(problem,c)}
                     for c in judge.cases if c.visibility=='public' and not c.passed]}
        content = analysis.AnalysisContent(**draft.model_dump(exclude={'code_observation'}),hints=analysis.safe_hints(problem,judge))
        record = {'id':active,'expected_issue':spec['expected_issue'],'started_at':now(),
                  'candidate':content.model_dump(exclude={'hints'}),'actual_issues':None,'passed':False}
        start = time.monotonic()
        try:
            async with asyncio.timeout(analysis.ANALYSIS_TIMEOUT):
                async with analysis.httpx.AsyncClient(timeout=httpx.Timeout(analysis.ANALYSIS_TIMEOUT,connect=5)) as client:
                    record['actual_issues'] = await analysis.review_hints(client,facts,content,[])
            record['passed'] = (spec['expected_issue'] in record['actual_issues'] if spec['expected_issue']
                                else not record['actual_issues'])
        except Exception as error:
            record['error_type'] = type(error).__name__
        record['seconds'] = round(time.monotonic()-start,3)
        gates.append(record)
        save('review-gate-results.json',{'status':'running','items':gates})
        print(json.dumps({'review_gate':active,'passed':record['passed'],'issues':record['actual_issues']},ensure_ascii=False),flush=True)
    save('review-gate-results.json',{'status':'complete','items':gates,'passed':sum(g['passed'] for g in gates),'total':len(gates)})
    for case in fixtures:
        active = case['trial_id']
        item = {'trial_id': active, 'started_at': now(), 'finished_at': None, 'result': None, 'checks': {}}
        report['trials'].append(item)
        save('real-ai-results.json', report)
        problem = PROBLEMS[case['problem_id']].execution_problem()
        if case['mode'] == 'run':
            problem = problem.model_copy(update={'tests':[TestCase(case_id='run', stdin=case['stdin'], expected_output='')]})
        start = time.monotonic()
        try:
            result = await analysis.analyze_failure(problem, case['code'], JudgeResult.model_validate(case['judge']),
                                                    execution_mode=case['mode'])
            item['result'] = result.model_dump(mode='json')
            item['checks']['expected_status'] = result.status == ('skipped' if case['expected_feedback_kind']=='skipped' else 'ready')
            if result.status == 'ready':
                item['checks']['route'] = result.feedback_kind == case['expected_feedback_kind']
                if result.content:
                    item['checks']['tag_allowed'] = result.content.misconception_tag in case['acceptable_tags']
        except Exception as error:
            item['error_type'] = type(error).__name__
            item['checks']['expected_status'] = False
        item['finished_at'] = now()
        item['seconds'] = round(time.monotonic()-start, 3)
        item['technical_passed'] = all(item['checks'].values())
        save('real-ai-results.json', report)
        print(json.dumps({'trial_id': active, 'status': (item['result'] or {}).get('status'), 'checks': item['checks']}, ensure_ascii=False), flush=True)
    report['finished_at'] = now()
    report['summary'] = {'trials': len(fixtures), 'statuses': dict(Counter((t['result'] or {}).get('status', 'error') for t in report['trials'])),
                         'technical_passed': sum(t['technical_passed'] for t in report['trials']),
                         'provider_attempts': len(calls), 'human_semantic_pass_rate': None}
    save('real-ai-results.json', report)
    usage = Counter()
    for call in calls:
        for key, value in ((call.get('response') or {}).get('usage') or {}).items():
            if isinstance(value, int):
                usage[key] += value
    save('provider-usage.json', dict(usage))
    print(json.dumps(report['summary'], ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='/evidence')
    args = parser.parse_args()
    OUT = Path(args.output)
    OUT.mkdir(parents=True, exist_ok=True)
    os.environ['AI_ACCEPTANCE_LOG'] = str(OUT/'acceptance.jsonl')
    asyncio.run(main())
