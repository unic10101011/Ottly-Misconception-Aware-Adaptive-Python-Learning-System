"""Temporary acceptance observer. Forward unchanged requests to fixed DeepSeek.

Only the current synthetic trial is recorded. Never persist headers, API keys,
reasoning_content, or unrelated application requests. No retries.
"""
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
import uuid

import httpx

EVIDENCE = Path('/evidence')
UPSTREAM = 'https://api.deepseek.com'
WRITE_LOCK = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def observed_trial(payload):
    try:
        context = json.loads((EVIDENCE / 'current-trial.json').read_text())
        facts, _ = json.JSONDecoder().raw_decode(payload['messages'][-1]['content'])
        code = facts['student_code']
        if hashlib.sha256(code.encode()).hexdigest() == context['code_sha256']:
            return context['trial_id']
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path != '/health':
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

    def do_POST(self):
        if self.path != '/chat/completions':
            self.send_error(404)
            return
        raw = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        payload = json.loads(raw)
        trial = observed_trial(payload)
        record = {'call_id': uuid.uuid4().hex, 'trial_id': trial, 'started_at': now(),
                  'upstream': UPSTREAM + self.path, 'request': payload,
                  'http_status': None, 'response': None, 'transport_error': None}
        started = time.monotonic()
        try:
            with httpx.Client(timeout=httpx.Timeout(100, connect=5)) as client:
                response = client.post(UPSTREAM + self.path, content=raw, headers={
                    'Authorization': self.headers.get('Authorization', ''),
                    'Content-Type': 'application/json'})
            record['http_status'] = response.status_code
            body = response.json()
            record['response'] = {k: body.get(k) for k in ('id', 'model', 'created', 'usage')}
            record['response']['choices'] = [{'finish_reason': c.get('finish_reason'),
                'message': {'content': (c.get('message') or {}).get('content')}} for c in body.get('choices', [])]
            status, result = response.status_code, response.content
        except Exception as error:
            record['transport_error'] = type(error).__name__
            status, result = 502, b'{"error":{"message":"acceptance observer transport failure"}}'
        record['seconds'] = round(time.monotonic() - started, 3)
        record['finished_at'] = now()
        if trial:
            with WRITE_LOCK:
                with (EVIDENCE / 'provider-calls.jsonl').open('a', encoding='utf-8') as target:
                    target.write(json.dumps(record, ensure_ascii=False) + '\n')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(result)))
        self.end_headers()
        try:
            self.wfile.write(result)
        except BrokenPipeError:
            pass


if __name__ == '__main__':
    assert UPSTREAM == 'https://api.deepseek.com'
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
