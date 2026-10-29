"""Execute the locked 120 trials over real application HTTP, exactly once.

Human oracles never enter request payloads. Synthetic account credentials remain
in memory. --resume skips every already-started trial; it never retries one.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import time

import httpx


HERE = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone.utc).isoformat()


def dump(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def records(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def call(client, method, path, payload=None, expected_code=200):
    started = time.monotonic()
    r = client.request(method, path, json=payload)
    r.raise_for_status()
    body = r.json()
    if body.get('code') != expected_code:
        raise RuntimeError('Unexpected application status at ' + path)
    return body['data'], round(time.monotonic() - started, 3)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', default='http://frontend')
    p.add_argument('--evidence-dir', required=True, type=Path)
    p.add_argument('--resume', action='store_true')
    a = p.parse_args()
    lock = json.loads((HERE/'design-lock.json').read_text(encoding='utf-8'))
    for f in lock['files']:
        assert hashlib.sha256((HERE/f['path']).read_bytes()).hexdigest() == f['sha256'], f['path']
    dataset = json.loads((HERE/'cases.json').read_text(encoding='utf-8'))
    runtime = json.loads((a.evidence_dir/'runtime-before.json').read_text(encoding='utf-8'))
    assert runtime['source_matches_baseline'] and runtime['key_configured']
    assert runtime['model'] == 'deepseek-flash'
    backend = Path('/workspace/backend')
    manifest = json.loads((HERE.parent/'layout-migration-2026-10-28/source-manifest.json').read_text(encoding='utf-8'))
    for f in manifest['files']:
        if f['path'].startswith('backend/app/'):
            content = (backend/Path(f['path']).relative_to('backend')).read_bytes().replace(b'\r\n', b'\n')
            assert hashlib.sha256(content).hexdigest() == f['sha256_lf'], f['path']
    levels = json.loads((backend/'app/data/levels.json').read_text(encoding='utf-8'))
    cases = dataset['cases']
    plan = [(r,c) for r in (1,2,3) for c in cases if r == 1 or c['id'] in dataset['repeat_case_ids']]
    output = a.evidence_dir/'responses.json'
    if output.exists():
        if not a.resume:
            raise SystemExit('Evidence exists; refusing to repeat trials. Use --resume to skip started trials.')
        report = json.loads(output.read_text(encoding='utf-8'))
        assert report['dataset_sha256'] == hashlib.sha256((HERE/'cases.json').read_bytes()).hexdigest()
    else:
        report = {'dataset_id': dataset['dataset_id'], 'dataset_sha256': hashlib.sha256((HERE/'cases.json').read_bytes()).hexdigest(),
                  'application_baseline': dataset['application_baseline'], 'started_at': now(), 'finished_at': None,
                  'status': 'running', 'real_ai': True, 'attempt_policy': 'One initial attempt per trial, no retries; cached reads are not new trials.',
                  'planned_trials': 120, 'planned_ai_feedback_trials': 104, 'trials': [], 'human_review': 'pending'}
    def save():
        dump(output, report)
    started_ids = {x['trial_id'] for x in report['trials']}
    for old in report['trials']:
        if old.get('completed_at') is None:
            old['interrupted_without_retry'] = True
    save()
    for rnd, case in plan:
        trial = f"{case['id']}-R{rnd}"
        if trial in started_ids:
            continue
        exp = case['expected']
        item = {'trial_id': trial, 'case_id': case['id'], 'round': rnd, 'started_at': now(), 'completed_at': None,
                'account': None, 'setup': [], 'submit_response': None, 'analysis_response': None, 'run_events': [],
                'final_analysis': None, 'checks': {}, 'timings_seconds': {}, 'error': None,
                'provider_call_ids': [], 'acceptance_record_ids': [], 'human_review': {}}
        report['trials'].append(item)
        acceptance_before = len(records(a.evidence_dir/'acceptance.jsonl'))
        dump(a.evidence_dir/'current-trial.json', {'trial_id': trial, 'code_sha256': case['code_sha256']})
        save()
        started = time.monotonic()
        with httpx.Client(base_url=a.url, timeout=httpx.Timeout(145, connect=5)) as client:
            try:
                nonce = secrets.token_hex(3)
                username = 'core72_' + nonce + '_' + trial.lower()
                password = secrets.token_urlsafe(24)
                phone = 'c72_' + nonce + '_' + trial.lower()
                registered, _ = call(client, 'POST', '/api/v1/auth/register',
                                      {'username': username, 'password': password, 'phone': phone}, 201)
                logged_in, _ = call(client, 'POST', '/api/v1/auth/login', {'username': username, 'password': password})
                client.headers['Authorization'] = 'Bearer ' + logged_in['access_token']
                item['account'] = {'username': username, 'user_id': registered['id']}
                for slot in levels[:case['level_no']-1]:
                    lesson = json.loads((backend/f"app/data/{slot['problem_id']}.json").read_text(encoding='utf-8'))
                    data, seconds = call(client,'POST','/api/v1/code/submit',
                                          {'problem_id': slot['problem_id'], 'code': lesson['reference_solution']})
                    if not data['judge']['passed'] or data['analysis']['status'] != 'skipped':
                        raise RuntimeError('Prerequisite failed; target was not attempted.')
                    item['setup'].append({'problem_id': slot['problem_id'], 'submission_id': data['submission_id'],
                                          'passed': True, 'analysis': 'skipped', 'seconds': seconds})
                item['timings_seconds']['setup'] = round(time.monotonic()-started,3)
                save()
                target_started = time.monotonic()
                analysis = None
                if case['mode'] == 'submit':
                    data, seconds = call(client,'POST','/api/v1/code/submit', {'problem_id': case['problem_id'], 'code': case['code']})
                    item['submit_response'] = data
                    item['timings_seconds']['submit'] = seconds
                    judge = data['judge']
                    item['checks']['judge_matches'] = all(judge[k] == exp[e] for k,e in
                        [('status','judge_status'),('passed_cases','passed_cases'),('total_cases','total_cases')])
                    item['checks']['first_target_submission_not_recommendation_eligible'] = not data['practice_recommendation_eligible']
                    item['checks']['hidden_details_redacted'] = all(not x['expected_output'] and not x['actual_output'] and not x['errors'] and not x['output_available'] for x in judge['cases'] if x['visibility']=='hidden')
                    if exp['error_code']:
                        item['checks']['public_error_matches'] = any(e['type']==exp['error_code'] for x in judge['cases'] if x['visibility']=='public' for e in x['errors'])
                    analysis = data['analysis']
                    save()
                    if analysis['status']=='preparing':
                        prepared, seconds = call(client,'POST',f"/api/v1/code/submissions/{data['submission_id']}/analysis")
                        item['analysis_response'] = prepared
                        item['timings_seconds']['feedback_endpoint'] = seconds
                        analysis = prepared['analysis']
                    item['timings_seconds']['target_end_to_end'] = round(time.monotonic()-target_started,3)
                    item['final_analysis'] = analysis
                    save()
                    before_cache = len(records(a.evidence_dir/'provider-calls.jsonl'))
                    cached, seconds = call(client,'POST',f"/api/v1/code/submissions/{data['submission_id']}/analysis")
                    item['checks']['saved_analysis_cache_identical'] = cached['analysis'] == analysis
                    item['checks']['cached_read_no_provider_call'] = len(records(a.evidence_dir/'provider-calls.jsonl')) == before_cache
                    item['timings_seconds']['cached_read'] = seconds
                    history, _ = call(client,'GET','/api/v1/code/submissions?limit=20')
                    saved = next((x for x in history['items'] if x['id']==data['submission_id']), None)
                    item['checks']['submission_and_feedback_saved'] = bool(saved and saved['analysis']==analysis)
                else:
                    before,_ = call(client,'GET','/api/v1/code/submissions?limit=1')
                    progress_before,_ = call(client,'GET','/api/v1/code/progress')
                    payload = {'problem_id':case['problem_id'], 'code':case['code'], 'stdin':case['stdin'], 'timeout':case['timeout_seconds']}
                    with client.stream('POST','/api/v1/code/run?stream_analysis=true',json=payload) as response:
                        response.raise_for_status()
                        for line in response.iter_lines():
                            if line.strip():
                                body=json.loads(line)
                                assert body['code']==200
                                item['run_events'].append(body)
                                if len(item['run_events'])==1:
                                    item['timings_seconds']['first_execution_event']=round(time.monotonic()-target_started,3)
                                    save()
                    assert item['run_events']
                    data=item['run_events'][-1]['data']
                    analysis=data.get('analysis')
                    item['final_analysis']=analysis
                    item['timings_seconds']['target_end_to_end']=round(time.monotonic()-target_started,3)
                    item['checks']['run_success_matches']=data['success']==exp['run_success']
                    item['checks']['run_output_matches']=data['output']==exp['output']
                    if exp['error_code']:
                        item['checks']['run_error_matches']=any(e['type']==exp['error_code'] for e in data['errors'])
                        item['checks']['run_judge_matches']=data['judge']['status']==exp['judge_status']
                        item['checks']['execution_stream_precedes_feedback']=item['run_events'][0]['data']['analysis']['status']=='preparing'
                    after,_=call(client,'GET','/api/v1/code/submissions?limit=1')
                    progress_after,_=call(client,'GET','/api/v1/code/progress')
                    item['checks']['run_created_no_submission']=before['total']==after['total']
                    item['checks']['run_did_not_change_progress']=progress_before==progress_after
                kind=exp['feedback_kind']
                if kind in {'diagnosis','guidance'}:
                    item['checks']['ai_ready']=bool(analysis and analysis.get('status')=='ready' and analysis.get('source')=='ai')
                    item['checks']['feedback_route_matches']=bool(analysis and analysis.get('feedback_kind')==kind)
                    item['checks']['feedback_shape_matches']=bool(analysis and (
                        bool(analysis.get('content')) and analysis.get('guidance') is None if kind=='diagnosis'
                        else bool(analysis.get('guidance')) and analysis.get('content') is None))
                elif kind=='skipped':
                    item['checks']['analysis_skipped']=analysis['status']=='skipped' and analysis.get('content') is None and analysis.get('guidance') is None
                else:
                    item['checks']['successful_run_has_no_analysis']=analysis is None
            except Exception as error:
                item['error']={'type':type(error).__name__,'message':str(error)[:500]}
                item['checks']['request_completed']=False
        calls=[r for r in records(a.evidence_dir/'provider-calls.jsonl') if r['trial_id']==trial]
        item['provider_call_ids']=[r['call_id'] for r in calls]
        item['acceptance_record_ids']=[r['record_id'] for r in records(a.evidence_dir/'acceptance.jsonl')[acceptance_before:]]
        expected_ai=exp['feedback_kind'] in {'diagnosis','guidance'}
        if not expected_ai:
            item['checks']['no_ai_call_for_control']=not calls
        item['provider_usage']=[r['response'].get('usage') for r in calls if r.get('response')]
        item['timings_seconds']['total_with_setup']=round(time.monotonic()-started,3)
        item['completed_at']=now()
        item['technical_passed']=bool(item['checks']) and all(item['checks'].values())
        save()
        print(trial,'status='+str((item['final_analysis'] or {}).get('status','no_analysis')),
              'technical='+str(item['technical_passed']),'calls='+str(len(calls)),
              'seconds='+str(item['timings_seconds']['total_with_setup']),flush=True)
    dump(a.evidence_dir/'current-trial.json', {})
    report['status']='completed'
    report['finished_at']=now()
    report['summary']={'trials':len(report['trials']),'technical_passed':sum(x.get('technical_passed',False) for x in report['trials']),
                       'analysis_statuses':dict(Counter((x.get('final_analysis') or {}).get('status','no_analysis') for x in report['trials'])),
                       'human_semantic_review':'pending'}
    save()
    print('DONE',json.dumps(report['summary'],ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
