"""Opt-in real HTTP check for personalized hints on an isolated backend."""
import json
from pathlib import Path
import secrets
import sys
import time

import httpx


URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000'
OUTPUT = Path(sys.argv[2] if len(sys.argv) > 2 else '/app/tests/live_personalized_acceptance.json')
RANGE = 'total = 0\nfor i in range(1, 100):\n    total += i\nprint(total)'
ACCUMULATION = 'total = 0\nfor i in range(1, 101):\n    total = i\nprint(total)'
VARIABLE = 'print(missing_total)'
CORRECT = 'total = 0\nfor i in range(1, 101):\n    total += i\nprint(total)'


def account(client):
    username = 'accept_' + secrets.token_hex(5)
    password = secrets.token_urlsafe(20)
    phone = '19' + str(secrets.randbelow(10**9)).zfill(9)
    registered = client.post('/api/v1/auth/register', json={
        'username': username, 'password': password, 'phone': phone,
    })
    registered.raise_for_status()
    assert registered.json()['code'] == 201, registered.text
    login = client.post('/api/v1/auth/login', json={'username': username, 'password': password})
    login.raise_for_status()
    return login.json()['data']['access_token']


def submit(client, token, name, code):
    headers = {'Authorization': 'Bearer ' + token}
    started = time.monotonic()
    response = client.post('/api/v1/code/submit', headers=headers,
                           json={'problem_id': 'level2', 'code': code})
    response.raise_for_status()
    data = response.json()['data']
    judge_seconds = round(time.monotonic() - started, 2)
    if data['analysis']['status'] == 'preparing':
        analyzed = client.post(f"/api/v1/code/submissions/{data['submission_id']}/analysis",
                               headers=headers)
        analyzed.raise_for_status()
        data['analysis'] = analyzed.json()['data']['analysis']
    analysis = data['analysis']
    content = analysis.get('content') or {}
    item = {
        'name': name,
        'judge_status': data['judge']['status'],
        'judge_cases': data['judge']['cases'],
        'judge_seconds': judge_seconds,
        'analysis_status': analysis['status'],
        'analysis_source': analysis.get('source'),
        'personalization': analysis.get('personalization'),
        'misconception_tag': content.get('misconception_tag'),
        'suspected_cause': content.get('suspected_cause'),
        'hints': content.get('hints'),
        'analysis_message': analysis.get('message'),
        'elapsed_seconds': round(time.monotonic() - started, 2),
    }
    print(name, item['judge_status'], item['analysis_status'], item['personalization'], flush=True)
    return item


def main():
    report = {'model': 'qwen2.5-coder:3b-instruct', 'cases': []}
    with httpx.Client(base_url=URL, timeout=180) as client:
        first = account(client)
        second = account(client)
        report['cases'].append(submit(client, first, 'first_range', RANGE))
        report['cases'].append(submit(client, second, 'other_user_range', RANGE))
        report['cases'].append(submit(client, first, 'second_accumulation', ACCUMULATION))
        report['cases'].append(submit(client, first, 'current_variable', VARIABLE))
        report['cases'].append(submit(client, first, 'later_correct', CORRECT))
        report['cases'].append(submit(client, first, 'after_correct_accumulation', ACCUMULATION))
        headers = {'Authorization': 'Bearer ' + first}
        history = client.get('/api/v1/code/submissions', headers=headers)
        history.raise_for_status()
        report['first_user_history_count'] = history.json()['data']['total']
        other_history = client.get('/api/v1/code/submissions',
                                   headers={'Authorization': 'Bearer ' + second})
        other_history.raise_for_status()
        report['other_user_history_count'] = other_history.json()['data']['total']
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Report saved:', OUTPUT, flush=True)


if __name__ == '__main__':
    main()
