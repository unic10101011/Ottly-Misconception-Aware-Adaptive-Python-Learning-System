"""Opt-in real HTTP/Ollama checks across the curriculum and run-error entry.

Creates an isolated test account. Reference solutions only unlock progression;
expected_cause is report-only and is never sent to the analysis endpoint.
Run from backend: python tests/live_global_analysis.py
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import time

import httpx


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:3000')
    parser.add_argument('--output', type=Path, default=ROOT.parent / 'docs/live-global-analysis.json')
    args = parser.parse_args()
    cases = json.loads((ROOT / 'tests/data/global_analysis_cases.json').read_text(encoding='utf-8'))
    account = {'username': 'global_ai_' + secrets.token_hex(5), 'password': secrets.token_urlsafe(20),
               'phone': '19' + str(secrets.randbelow(10**9)).zfill(9)}
    report = {'tested_at': datetime.now(timezone.utc).isoformat(), 'cases': []}

    def save(item):
        report['cases'].append(item)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(item['name'], item['analysis'].get('status'), item['analysis'].get('source'),
              item['analysis'].get('content', {}).get('suspected_cause') if item['analysis'].get('content') else '', flush=True)

    with httpx.Client(base_url=args.url, timeout=180) as client:
        response = client.post('/api/v1/auth/register', json=account)
        response.raise_for_status()
        assert response.json()['code'] == 201
        response = client.post('/api/v1/auth/login', json=account)
        response.raise_for_status()
        client.headers['Authorization'] = 'Bearer ' + response.json()['data']['access_token']
        for case in cases:
            problem_id = case['problem_id']
            lesson = json.loads((ROOT / f'app/data/{problem_id}.json').read_text(encoding='utf-8'))
            code = case.get('code')
            if code is None:
                old, new = case['replace']
                assert old in lesson['reference_solution']
                code = lesson['reference_solution'].replace(old, new, 1)
            started = time.monotonic()
            response = client.post('/api/v1/code/submit', json={'problem_id': problem_id, 'code': code})
            response.raise_for_status()
            data = response.json()['data']
            assert not data['judge']['passed'], problem_id
            judge_seconds = round(time.monotonic() - started, 2)
            response = client.post(f"/api/v1/code/submissions/{data['submission_id']}/analysis")
            response.raise_for_status()
            data['analysis'] = response.json()['data']['analysis']
            partial = 0 < data['judge']['passed_cases'] < data['judge']['total_cases']
            analysis = data['analysis']
            route_ok = (analysis.get('feedback_kind') == 'guidance' and analysis.get('content') is None
                        and bool(analysis.get('guidance'))) if partial else (
                        analysis.get('feedback_kind') == 'diagnosis' and bool(analysis.get('content')))
            save({'name': problem_id, 'code': code, 'expected_cause': case['expected_cause'],
                  'judge_seconds': judge_seconds, 'route_passed': route_ok,
                  'timings': response.json()['data']['timings'],
                  'seconds': round(time.monotonic() - started, 2), 'judge': data['judge'], 'analysis': data['analysis']})
            response = client.post('/api/v1/code/submit', json={
                'problem_id': problem_id, 'code': lesson['reference_solution']})
            response.raise_for_status()
            correct = response.json()['data']
            assert correct['judge']['passed'] and correct['analysis']['status'] == 'skipped', problem_id
        for name, payload in [
            ('run-invalid-input', {'problem_id': 'shell-shop-v1', 'code': 'price=int(input())', 'stdin': 'abc\n'}),
            ('run-free-practice', {'code': 'print(missing_value)', 'stdin': ''}),
            ('run-syntax-error', {'code': 'if True\n    print(1)', 'stdin': ''}),
        ]:
            started = time.monotonic()
            response = client.post('/api/v1/code/run', json={**payload, 'timeout': 3})
            response.raise_for_status()
            data = response.json()['data']
            assert data['success'] is False and data['errors'], name
            analysis = data.get('analysis', {})
            save({'name': name, 'code': payload['code'], 'stdin': payload['stdin'],
                  'route_passed': analysis.get('feedback_kind') == 'diagnosis' and bool(analysis.get('content')),
                  'seconds': round(time.monotonic() - started, 2), 'judge': data.get('judge'),
                  'analysis': analysis})
    assert all(item['analysis'].get('status') == 'ready' and item['analysis'].get('source') == 'ai'
               and item.get('route_passed', True)
               for item in report['cases']), 'Some cases did not return valid real AI feedback for their route; see report'


if __name__ == '__main__':
    main()
