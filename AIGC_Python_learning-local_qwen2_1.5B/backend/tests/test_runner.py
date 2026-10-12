from concurrent.futures import ThreadPoolExecutor
import time


def run(code, timeout=3):
    from app.services.sandbox.runner import run_code_process

    return run_code_process(code, timeout=timeout)


def test_runner_preserves_normal_output():
    result = run("print('你好，Python!')")
    assert result['success'] is True
    assert result['output'] == '你好，Python!\n'
    assert result['output_available'] is True
    assert result['errors'] == []


def test_syntax_error_has_line_number_and_no_fake_stdout():
    result = run('for i in range(3)\n    print(i)')
    assert result['success'] is False
    assert result['output'] == ''
    assert result['errors'][0]['type'] == '语法错误'
    assert result['errors'][0]['line'] == 1


def test_runtime_error_preserves_output_and_error_evidence():
    result = run("print('before')\nprint(1 / 0)")
    assert result['success'] is False
    assert result['output'] == 'before\n'
    assert result['errors'][0]['type'] == 'ZeroDivisionError'
    assert result['errors'][0]['line'] == 2


def test_timeout_terminates_worker_and_next_run_succeeds():
    started = time.monotonic()
    result = run("print('before timeout')\nwhile True:\n    pass", timeout=1)
    assert time.monotonic() - started < 4
    assert result['success'] is False
    assert result['errors'][0]['type'] == '超时警告'
    assert result['output_available'] is False
    recovered = run("print('ready')")
    assert recovered['success'] is True
    assert recovered['output'] == 'ready\n'


def test_excess_output_stops_with_bounded_evidence():
    result = run("while True:\n    print('x' * 1000)")
    assert result['success'] is False
    assert result['errors'][0]['type'] == 'OutputLimitError'
    assert len(result['output']) <= 8000


def test_concurrent_runs_do_not_mix_stdout():
    def request(label):
        return run(f"import time\nfor i in range(3):\n    print('{label}')\n    time.sleep(0.05)")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(request, ['alpha', 'beta']))
    assert [result['success'] for result in results] == [True, True]
    assert [result['output'] for result in results] == ['alpha\n' * 3, 'beta\n' * 3]


def test_security_rejection_has_no_fake_stdout():
    result = run('import os')
    assert result['success'] is False
    assert result['output'] == ''
    assert result['errors'][0]['type'] == '安全警告'


def test_worker_start_failure_marks_output_unknown(monkeypatch):
    from app.services.sandbox import runner

    def fail_to_start(*args, **kwargs):
        raise OSError('worker unavailable')

    monkeypatch.setattr(runner.subprocess, 'run', fail_to_start)
    result = run("print('not executed')")
    assert result['success'] is False
    assert result['errors'][0]['type'] == 'RunnerError'
    assert result['output_available'] is False
