"""Run the existing sandbox in a disposable process with a hard deadline.

This protects the local demo from stuck threads and shared stdout. It does not
provide an OS security boundary for hostile code.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


BACKEND_ROOT = Path(__file__).resolve().parents[3]


def run_code_process(code: str, timeout: int = 3) -> dict:
    started = time.monotonic()
    # Keep runtime necessities only; never inherit application DB/JWT secrets.
    env = {
        key: value for key, value in os.environ.items()
        if key.upper() in {'SYSTEMROOT', 'WINDIR', 'SYSTEMDRIVE', 'TEMP', 'TMP', 'PATH', 'LD_LIBRARY_PATH'}
    }
    env.update(PYTHONIOENCODING='utf-8', PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    try:
        completed = subprocess.run(
            [sys.executable, '-m', 'app.services.sandbox.worker'],
            input=json.dumps({'code': code, 'timeout': timeout}, ensure_ascii=False),
            cwd=BACKEND_ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0:
            raise ValueError('Worker did not return a result')
        result = json.loads(completed.stdout)
        if not isinstance(result, dict) or not {'success', 'output', 'errors', 'execution_time'} <= result.keys():
            raise ValueError('Invalid worker result')
        result['output_available'] = True
        return result
    except subprocess.TimeoutExpired:
        error_type = '超时警告'
        message = f'代码执行超过 {timeout} 秒，执行进程已终止'
        suggestion = '检查循环终止条件或减少计算量'
    except (OSError, ValueError):
        error_type = 'RunnerError'
        message = '代码执行器暂时不可用，请稍后重试'
        suggestion = '请检查后端运行环境'
    return {
        'success': False,
        'output': '',
        'output_available': False,
        'errors': [{'type': error_type, 'line': None, 'column': None, 'message': message, 'suggestion': suggestion}],
        'execution_time': round(time.monotonic() - started, 3),
    }
