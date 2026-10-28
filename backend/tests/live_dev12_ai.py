"""Opt-in real HTTP/AI development run. Human standards never enter API payloads.

Creates three synthetic accounts and retains their learning records for audit.
No automatic retries or changes to prompts. Outputs contain no credentials.
"""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import secrets
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def source_hash():
    digest = hashlib.sha256()
    for path in sorted([*ROOT.glob('app/**/*.py'), *ROOT.glob('app/data/**/*.json')]):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
    return digest.hexdigest()


def call(client, method, path, payload=None):
    started = time.monotonic()
    response = client.request(method, path, json=payload)
    duration = round(time.monotonic() - started, 3)
    response.raise_for_status()
    body = response.json()
    if body.get('code') != 200:
        raise RuntimeError(f'API operation failed at {path}')
    return body['data'], duration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://frontend')
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--git-head', default='unknown')
    parser.add_argument('--runtime-hash', required=True)
    parser.add_argument('--runtime-image', default='unknown')
    parser.add_argument('--cases', nargs='+', help='Run only these case IDs in dataset order; never retry automatically.')
    args = parser.parse_args()
    cases = json.loads((ROOT / 'tests/data/dev12_ai_cases.json').read_text(encoding='utf-8'))
    if args.cases:
        unknown = set(args.cases) - {case['id'] for case in cases}
        if unknown:
            raise SystemExit('Unknown case IDs: ' + ', '.join(sorted(unknown)))
        # D11 depends on the preceding D02 failure for the same account.
        if 'D11' in args.cases and 'D02' not in args.cases:
            raise SystemExit('D11 requires D02 in the same run.')
        cases = [case for case in cases if case['id'] in args.cases]
    fingerprint = source_hash()
    if fingerprint != args.runtime_hash:
        raise SystemExit('Source differs from the running backend. Freeze the version before testing.')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / 'responses.json'
    if output.exists():
        raise SystemExit('Refusing to overwrite a previous test run.')
    report = {
        'started_at': now(), 'finished_at': None, 'status': 'running',
        'local_date': datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d'),
        'git_head': args.git_head, 'working_tree_has_uncommitted_security_fixes': True,
        'source_sha256': fingerprint, 'runtime_image': args.runtime_image,
        'model_request_name': 'deepseek-flash', 'real_api': True,
        'model_configuration': {'thinking': 'enabled', 'reasoning_effort': 'high', 'max_tokens': 8192},
        'attempt_policy': 'One initial attempt per case. No automatic retries.',
        'capture_scope': 'Complete application HTTP responses, not discarded provider candidates or reasoning.',
        'selected_cases': [case['id'] for case in cases],
        'usage': None, 'usage_note': 'The current application API does not expose provider usage or cost. model_load_ms=0 is not a measured model duration.',
        'accounts': [], 'setup': [], 'cases': [],
        'human_review_status': 'pending',
    }
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    save()
    nonce = secrets.token_hex(4)
    with ExitStack() as stack:
        clients = {}
        for label in sorted({case['account'] for case in cases}):
            client = stack.enter_context(httpx.Client(base_url=args.url, timeout=httpx.Timeout(150, connect=5)))
            username = f'dev12_{nonce}_{label.lower()}'
            password = secrets.token_urlsafe(24)
            response = client.post('/api/v1/auth/register', json={
                'username': username, 'password': password, 'phone': f'test_{nonce}_{label.lower()}'})
            response.raise_for_status()
            if response.json().get('code') != 201:
                raise RuntimeError('Synthetic account registration failed')
            user_id = response.json()['data']['id']
            response = client.post('/api/v1/auth/login', json={'username': username, 'password': password})
            response.raise_for_status()
            client.headers['Authorization'] = 'Bearer ' + response.json()['data']['access_token']
            report['accounts'].append({'label': label, 'username': username, 'user_id': user_id})
            clients[label] = client
            save()
        levels = json.loads((ROOT / 'app/data/levels.json').read_text(encoding='utf-8'))
        for label, slots in [('A', levels), ('B', levels[:1])]:
            if label not in clients:
                continue
            for slot in slots:
                problem_id = slot['problem_id']
                lesson = json.loads((ROOT / f'app/data/{problem_id}.json').read_text(encoding='utf-8'))
                data, seconds = call(clients[label], 'POST', '/api/v1/code/submit',
                                     {'problem_id': problem_id, 'code': lesson['reference_solution']})
                if not data['judge']['passed'] or data['analysis']['status'] != 'skipped':
                    raise RuntimeError(f'Prerequisite setup failed: {label} {problem_id}')
                report['setup'].append({'account': label, 'problem_id': problem_id,
                                        'submission_id': data['submission_id'], 'seconds': seconds,
                                        'passed': True, 'analysis_status': 'skipped'})
                save()
        print('SETUP completed for accounts: ' + ', '.join(clients), flush=True)
        for case in cases:
            item = {**case, 'started_at': now(), 'completed_at': None,
                    'http_response': None, 'analysis_http_response': None,
                    'recommendation_http_response': None, 'checks': {},
                    'timings_seconds': {}, 'transport_error': None,
                    'human_review': {'correctness': '', 'evidence': '', 'tag_or_recommendation': '',
                                     'readability': '', 'answer_protection': '', 'conclusion': '', 'notes': ''}}
            report['cases'].append(item)
            save()
            client = clients[case['account']]
            started = time.monotonic()
            try:
                if case['mode'] == 'run':
                    before, _ = call(client, 'GET', '/api/v1/code/submissions?limit=1')
                    progress_before, _ = call(client, 'GET', '/api/v1/code/progress')
                    events = []
                    with client.stream('POST', '/api/v1/code/run?stream_analysis=true', json={
                            'problem_id': case['problem_id'], 'code': case['code'],
                            'stdin': case['stdin'], 'timeout': 3}) as response:
                        response.raise_for_status()
                        for line in response.iter_lines():
                            if not line.strip():
                                continue
                            body = json.loads(line)
                            if body.get('code') != 200:
                                raise RuntimeError('Run stream returned an error')
                            events.append(body)
                            if len(events) == 1:
                                item['timings_seconds']['first_execution_event'] = round(time.monotonic() - started, 3)
                                item['stream_events'] = list(events)
                                save()
                    if not events:
                        raise RuntimeError('Run stream was empty')
                    item['stream_events'] = events
                    data = events[-1]['data']
                    item['http_response'] = {'code': 200, 'data': data}
                    analysis = data.get('analysis', {})
                    after, _ = call(client, 'GET', '/api/v1/code/submissions?limit=1')
                    progress_after, _ = call(client, 'GET', '/api/v1/code/progress')
                    item['checks']['run_created_no_submission'] = before['total'] == after['total']
                    item['checks']['run_did_not_change_progress'] = progress_before == progress_after
                    item['checks']['actual_value_error'] = any(e['type'] == 'VALUE_ERROR' for e in data['errors'])
                    item['checks']['empty_stdout'] = data['output'] == ''
                    item['checks']['execution_before_analysis'] = events[0]['data'].get('analysis', {}).get('status') == 'preparing'
                else:
                    data, seconds = call(client, 'POST', '/api/v1/code/submit',
                                         {'problem_id': case['problem_id'], 'code': case['code']})
                    item['http_response'] = {'code': 200, 'data': data}
                    item['timings_seconds']['submit'] = seconds
                    judge = data['judge']
                    expected = case['expected']
                    item['checks']['judge_matches'] = (judge['status'] == expected['judge_status']
                        and judge['passed_cases'] == expected['passed_cases'] and judge['total_cases'] == expected['total_cases'])
                    analysis = data['analysis']
                    save()
                    print(f"{case['id']} judge={judge['status']} {judge['passed_cases']}/{judge['total_cases']}", flush=True)
                    if analysis['status'] == 'preparing':
                        prepared, seconds = call(client, 'POST', f"/api/v1/code/submissions/{data['submission_id']}/analysis")
                        item['analysis_http_response'] = {'code': 200, 'data': prepared}
                        item['timings_seconds']['feedback_endpoint'] = seconds
                        analysis = prepared['analysis']
                    if case['id'] in {'D11', 'D12'}:
                        recommendation, seconds = call(client, 'POST', f"/api/v1/code/submissions/{data['submission_id']}/practice-recommendation")
                        item['recommendation_http_response'] = {'code': 200, 'data': recommendation}
                        item['timings_seconds']['recommendation_endpoint'] = seconds
                        eligible = bool(data.get('practice_recommendation_eligible'))
                        item['checks']['recommendation_eligibility_matches'] = eligible == (case['id'] == 'D11')
                        if case['id'] == 'D11':
                            selected = recommendation.get('recommendation') or {}
                            catalog, _ = call(client, 'GET', '/api/v1/code/practice')
                            match = next((x for x in catalog['items'] if x['problem_id'] == selected.get('problem_id')), None)
                            item['selected_practice_metadata'] = match
                            item['checks']['recommendation_available_and_unpassed'] = bool(match and match['available'] and not match['completed'])
                            cached, cache_seconds = call(client, 'POST', f"/api/v1/code/submissions/{data['submission_id']}/practice-recommendation")
                            item['checks']['recommendation_cache_matches'] = cached == recommendation
                            item['timings_seconds']['recommendation_cached_read'] = cache_seconds
                        else:
                            item['checks']['recommendation_skipped'] = recommendation['status'] == 'skipped'
                item['final_analysis'] = analysis
                kind = case['expected']['feedback_kind']
                if kind in {'diagnosis', 'guidance'}:
                    item['checks']['real_ai_feedback_ready'] = analysis.get('status') == 'ready' and analysis.get('source') == 'ai'
                    item['checks']['feedback_route_matches'] = analysis.get('feedback_kind') == kind
                    item['checks']['feedback_shape_matches'] = (bool(analysis.get('content')) and analysis.get('guidance') is None
                        if kind == 'diagnosis' else bool(analysis.get('guidance')) and analysis.get('content') is None)
                else:
                    item['checks']['error_analysis_skipped'] = analysis.get('status') == 'skipped' and analysis.get('content') is None
            except Exception as error:
                item['transport_error'] = {'type': type(error).__name__, 'message': str(error)[:600]}
                item['checks']['request_completed'] = False
                print(f"{case['id']} request_error={type(error).__name__}", flush=True)
            item['timings_seconds']['case_total'] = round(time.monotonic() - started, 3)
            item['completed_at'] = now()
            item['technical_passed'] = bool(item['checks']) and all(item['checks'].values())
            save()
            print(f"{case['id']} analysis={(item.get('final_analysis') or {}).get('status')} technical={item['technical_passed']} seconds={item['timings_seconds']['case_total']}", flush=True)
    report['finished_at'] = now()
    report['status'] = 'completed'
    report['summary'] = {'cases': len(report['cases']),
                         'technical_passed': sum(c['technical_passed'] for c in report['cases']),
                         'human_semantic_review': 'pending'}
    save()
    print('DONE ' + json.dumps(report['summary'], ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
