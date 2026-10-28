"""Separate-process trace collector. Keeps already flushed steps when the worker is killed."""
import json
import os
import subprocess
import sys

from .runner import BACKEND_ROOT
from .limits import ExecutionBusy, execution_slot


def collect_trace(raw, interrupted=False):
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', errors='replace')
    result = {'line_semantics': 'before_execution', 'steps': [], 'exception': None,
              'trace_status': 'timeout' if interrupted else 'truncated', 'truncated': True,
              'truncation_reason': 'wall_time_limit' if interrupted else 'worker_limit'}
    for line in (raw or '').split('\n'):
        try:
            message = json.loads(line)
        except (ValueError, TypeError):
            continue  # A killed process may leave an incomplete final line.
        if message.get('kind') == 'step' and len(result['steps']) < 300:
            result['steps'].append({key: value for key, value in message.items() if key != 'kind'})
        elif message.get('kind') == 'result' and not interrupted:
            result.update({key: value for key, value in message.items() if key != 'kind'})
    return result


def run_trace_process(code, stdin, timeout=3, *, supports_text=False, supports_structures=False):
    try:
        with execution_slot():
            return _run_trace_process(code, stdin, timeout, supports_text=supports_text,
                                      supports_structures=supports_structures)
    except ExecutionBusy:
        return {'line_semantics': 'before_execution', 'steps': [], 'exception': None,
                'trace_status': 'unavailable', 'truncated': False, 'truncation_reason': None}


def _run_trace_process(code, stdin, timeout, *, supports_text, supports_structures):
    env = {key: value for key, value in os.environ.items()
           if key.upper() in {'SYSTEMROOT', 'WINDIR', 'SYSTEMDRIVE', 'TEMP', 'TMP', 'PATH', 'LD_LIBRARY_PATH'}}
    env.update(PYTHONIOENCODING='utf-8', PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    try:
        completed = subprocess.run([sys.executable, '-m', 'app.services.sandbox.trace_worker'],
                                   input=json.dumps({'code': code, 'stdin': stdin, 'supports_text': supports_text,
                                                     'supports_structures': supports_structures}), cwd=BACKEND_ROOT,
                                   env=env, capture_output=True, text=True, encoding='utf-8', timeout=timeout)
        return collect_trace(completed.stdout)
    except subprocess.TimeoutExpired as error:
        return collect_trace(error.stdout, interrupted=True)
    except OSError:
        return {'line_semantics': 'before_execution', 'steps': [], 'exception': None,
                'trace_status': 'unavailable', 'truncated': False, 'truncation_reason': None}
