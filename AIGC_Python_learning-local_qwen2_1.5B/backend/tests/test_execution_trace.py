import pytest

WRONG = 'n = int(input())\ntotal = 0\nfor i in range(1, n + 1):\n    total = i\nprint(total)\n'


def test_real_line_semantics_and_final_output():
    from app.services.sandbox.trace_runner import run_trace_process
    wrong = run_trace_process(WRONG, '3\n')
    assert wrong['trace_status'] == 'completed'
    assert wrong['line_semantics'] == 'before_execution'
    line4 = [step for step in wrong['steps'] if step['event'] == 'line' and step['line'] == 4]
    assert [(step['variables']['i'], step['variables']['total']) for step in line4] == [('1', '0'), ('2', '1'), ('3', '2')]
    assert wrong['steps'][-1]['event'] == 'end'
    assert wrong['steps'][-1]['stdout'] == '3\n'
    assert wrong['steps'][-1]['variables']['total'] == '3'
    correct = run_trace_process(WRONG.replace('total = i', 'total += i'), '3\n')
    assert correct['steps'][-1]['stdout'] == '6\n'
    assert line4[0]['variables']['total'] == '0', 'old snapshots cannot change later'


def test_zero_input_errors_limits_and_unsupported_syntax():
    from app.services.sandbox.trace_runner import run_trace_process
    assert run_trace_process(WRONG, '0\n')['steps'][-1]['stdout'] == '0\n'
    runtime = run_trace_process('x = 1\nprint(missing)\n', '3\n')
    assert runtime['trace_status'] == 'runtime_error'
    assert runtime['exception']['type'] == 'NameError'
    assert runtime['exception']['line'] == 2
    assert runtime['steps'][-1]['event'] == 'exception'
    syntax = run_trace_process('for i in range(3)\n    print(i)', '3\n')
    assert syntax['trace_status'] == 'syntax_error'
    assert syntax['steps'] == []
    assert syntax['exception']['line'] == 1
    compile_error = run_trace_process('break', '3\n')
    assert compile_error['trace_status'] == 'syntax_error'
    assert compile_error['steps'] == [] and compile_error['exception']['line'] == 1
    loop = run_trace_process('n = 0\nwhile True:\n    n += 1\n', '3\n')
    assert loop['trace_status'] == 'truncated'
    assert loop['truncated'] and loop['truncation_reason'] == 'step_limit'
    assert 0 < len(loop['steps']) <= 300
    for code in ['import os', 'print((1).__class__)', 'print("x" * 100000000)', 'def f():\n    return 1', 'print(2 ** 100000000)']:
        result = run_trace_process(code, '3\n')
        assert result['trace_status'] == 'unsupported'
        assert result['steps'] == []


def test_partial_steps_survive_hard_timeout_and_resource_limits(monkeypatch):
    import json
    import subprocess
    from app.services.sandbox import trace_runner
    huge = trace_runner.run_trace_process('x = 1000000\nwhile True:\n    x *= x\n', '3\n')
    assert huge['truncated'] and huge['truncation_reason'] == 'integer_limit'
    same_line = trace_runner.run_trace_process('x=1000000; ' + 'x*=x; ' * 15 + 'x=0', '3\n')
    assert same_line['trace_status'] == 'unsupported' and same_line['steps'] == []
    printing = 'for i in range(1000):\n    print(' + ','.join(['1000000'] * 20) + ')\n'
    result = trace_runner.run_trace_process(printing, '3\n')
    assert result['truncated'] and result['truncation_reason'] == 'output_limit'
    first = {'kind': 'step', 'step': 1, 'event': 'line', 'line': 1, 'variables': {}, 'stdout': ''}
    def timeout(*args, **kwargs):
        assert 'DATABASE_URL' not in kwargs['env'] and 'JWT_SECRET' not in kwargs['env']
        raise subprocess.TimeoutExpired(args[0], 3, output=(json.dumps(first) + '\n{').encode())
    monkeypatch.setattr(trace_runner.subprocess, 'run', timeout)
    result = trace_runner.run_trace_process('while True:\n    pass', '3\n')
    assert result['trace_status'] == 'timeout'
    assert result['truncated'] and len(result['steps']) == 1


def test_endpoint_replays_owned_submission_and_never_judges(client, monkeypatch):
    from app.api import execution_trace
    from app.models.learning_submission import LearningSubmission
    from app.core.database import get_db
    from main import app
    from test_learning_history import account
    headers = account(client, 'trace_owner', '13800000401')
    other = account(client, 'trace_other', '13800000402')
    assert client.post('/api/v1/code/execution-trace', json={}).status_code == 401
    body = {'problem_id': 'shell-total-v1', 'code': WRONG, 'stdin': '3\n'}
    assert client.post('/api/v1/code/execution-trace', headers=headers, json=body).status_code == 403
    monkeypatch.setattr(execution_trace, 'passed_problem_ids', lambda db, user: {'coastal-markers-v1'})
    response = client.post('/api/v1/code/execution-trace', headers=headers, json=body)
    assert response.status_code == 200, response.text
    data = response.json()['data']
    assert data['code'] == WRONG and data['code_source'] == 'draft'
    assert data['stdin'] == '3\n' and data['steps'][-1]['stdout'] == '3\n'
    assert client.get('/api/v1/code/submissions', headers=headers).json()['data']['total'] == 0
    assert client.get('/api/v1/code/progress', headers=headers).json()['data']['passed_problem_ids'] == []
    assert client.post('/api/v1/code/execution-trace', headers=headers, json={**body, 'stdin': '101\n'}).status_code == 422
    assert client.post('/api/v1/code/execution-trace', headers=headers, json={**body, 'problem_id': 'unsupported-v1'}).status_code == 422
    # Seed only the isolated test database, with no real judging or model requests.
    user_id = client.get('/api/v1/auth/me', headers=headers).json()['data']['id']
    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    row = LearningSubmission(user_id=user_id, problem_id='shell-total-v1', problem_title='sum',
                             problem_description='sum', code=WRONG, judge_json={}, analysis_json={}, passed=False)
    db.add(row); db.commit(); db.refresh(row)
    submission_id = row.id
    gen.close()
    payload = {'problem_id': 'shell-total-v1', 'submission_id': submission_id, 'stdin': '3\n'}
    result = client.post('/api/v1/code/execution-trace', headers=headers, json=payload)
    assert result.status_code == 200, result.text
    assert result.json()['data']['code_source'] == 'submission'
    assert result.json()['data']['code'] == WRONG
    assert client.post('/api/v1/code/execution-trace', headers=other, json=payload).status_code == 404
    assert client.post('/api/v1/code/execution-trace', headers=headers, json={**payload, 'code': 'print(6)'}).status_code == 422


from test_learning_history import client


def test_first_four_real_outputs_and_string_limits():
    from app.services.sandbox.trace_runner import run_trace_process
    from app.services.problem_catalog import LEVELS, PROBLEMS
    comment = run_trace_process('# 还没开始写代码\n', '', supports_text=True)
    assert comment['trace_status'] == 'completed'
    assert all(step['event'] != 'line' or step['line'] > 0 for step in comment['steps'])
    for slot in LEVELS[:4]:
        lesson = PROBLEMS[slot.problem_id]
        example = lesson.examples[0]
        result = run_trace_process(lesson.reference_solution, example.stdin, supports_text=True)
        assert result['trace_status'] == 'completed', result
        assert result['steps'][-1]['stdout'] == example.stdout
    greeting = run_trace_process('name = input()\nprint("Hello,", name + "!")', 'Li Ming\n', supports_text=True)
    assert greeting['steps'][1]['variables']['name'] == "'Li Ming'"
    assert greeting['steps'][-1]['stdout'] == 'Hello, Li Ming!\n'
    unicode_name = run_trace_process('name = input()\nprint(name)', 'A\u2028B\u2029C\u0085D\n', supports_text=True)
    assert unicode_name['trace_status'] == 'completed'
    assert unicode_name['steps'][-1]['event'] == 'end'
    assert unicode_name['steps'][-1]['stdout'] == 'A\u2028B\u2029C\u0085D\n'
    missing_conversion = run_trace_process('price = input()\nquantity = input()\nprint(price + quantity)', '4\n3\n', supports_text=True)
    assert missing_conversion['steps'][-1]['stdout'] == '43\n'
    division = run_trace_process('n = 17\nk = 5\nprint(n / k)', '', supports_text=True)
    assert division['steps'][-1]['stdout'] == '3.4\n'
    zero = run_trace_process('n = 17\nk = 0\nprint(n // k)', '', supports_text=True)
    assert zero['trace_status'] == 'runtime_error' and zero['exception']['line'] == 3
    for code in ['s = "a"\nn = 1000000 * 1000000\nprint(s * n)', 's = "a"\nn = 1000000 * 1000000\nprint(n * s)', 's = "%1000000000s"\nprint(s % "a")']:
        limited = run_trace_process(code, '', supports_text=True)
        assert limited['trace_status'] in {'truncated', 'runtime_error'} and limited['steps'][-1]['stdout'] == ''


def test_first_four_api_inputs_and_existing_unlock_rules(client, monkeypatch):
    from app.api import execution_trace
    from app.services.problem_catalog import LEVELS, PROBLEMS
    from test_learning_history import account
    headers = account(client, 'trace_four', '13800000403')
    first = {'problem_id': 'level1', 'code': "print('Hello, World!')", 'stdin': ''}
    result = client.post('/api/v1/code/execution-trace', headers=headers, json=first)
    assert result.status_code == 200 and result.json()['data']['stdin'] == ''
    assert result.json()['data']['problem_title'] == '第 1 关 · 初识小海獭'
    body = {'problem_id': 'shell-shop-v1', 'code': PROBLEMS['shell-shop-v1'].reference_solution, 'stdin': '4\n3\n20\n'}
    assert client.post('/api/v1/code/execution-trace', headers=headers, json=body).status_code == 403
    monkeypatch.setattr(execution_trace, 'passed_problem_ids', lambda db, user: {s.problem_id for s in LEVELS[:4]})
    for slot in LEVELS[:4]:
        lesson = PROBLEMS[slot.problem_id]
        sample = lesson.examples[0]
        data = client.post('/api/v1/code/execution-trace', headers=headers, json={
            'problem_id': lesson.problem_id, 'code': lesson.reference_solution, 'stdin': sample.stdin,
        })
        assert data.status_code == 200, data.text
        assert data.json()['data']['steps'][-1]['stdout'] == sample.stdout
    # Preserve the learner's exact string input, including surrounding spaces.
    name = client.post('/api/v1/code/execution-trace', headers=headers, json={
        'problem_id': 'greeting-v1', 'code': 'name = input()\nprint(name)', 'stdin': ' Li Ming \n',
    }).json()['data']
    assert name['stdin'] == ' Li Ming \n' and name['steps'][-1]['stdout'] == ' Li Ming \n'
    bad = client.post('/api/v1/code/execution-trace', headers=headers, json={**body, 'stdin': 'not-a-number\n3\n20\n'})
    assert bad.status_code == 200 and bad.json()['data']['trace_status'] == 'runtime_error'
    assert client.post('/api/v1/code/execution-trace', headers=headers, json={**body, 'stdin': 'x' * 2001}).status_code == 422
    assert client.get('/api/v1/code/submissions', headers=headers).json()['data']['total'] == 0


def test_all_lesson_examples_and_list_snapshots():
    from app.services.sandbox.trace_runner import run_trace_process
    from app.services.problem_catalog import LEVELS, PROBLEMS
    for slot in LEVELS:
        lesson = PROBLEMS[slot.problem_id]
        for sample in lesson.examples:
            result = run_trace_process(lesson.reference_solution, sample.stdin, supports_text=True, supports_structures=True)
            assert result['trace_status'] == 'completed', (slot.id, result)
            assert result['steps'][-1]['stdout'] == sample.stdout, slot.id
    result = run_trace_process('values = []\nvalues.append(2)\nvalues.append(9)\nprint(values[1])', '', supports_text=True, supports_structures=True)
    assert result['steps'][1]['variables']['values'] == '[]'
    assert result['steps'][2]['variables']['values'] == '[2]'
    assert result['steps'][-1]['variables']['values'] == '[2, 9]'


def test_function_calls_returns_errors_and_limits():
    from app.services.sandbox.trace_runner import run_trace_process
    options = dict(supports_text=True, supports_structures=True)
    code = 'def f(x):\n    y = x + 1\n    return y\na = f(1)\nb = f(5)\nprint(a, b)'
    result = run_trace_process(code, '', **options)
    assert result['trace_status'] == 'completed' and result['steps'][-1]['stdout'] == '2 6\n'
    calls = [s for s in result['steps'] if s['event'] == 'call']
    returns = [s for s in result['steps'] if s['event'] == 'return']
    assert len(calls) == len(returns) == 2
    assert calls[0]['scope_id'] != calls[1]['scope_id']
    assert [s['return_value'] for s in returns] == ['2', '6']
    assert all(s['function'] == 'f' for s in calls)
    broken = run_trace_process('def f(x):\n    return x // 0\nprint(f(1))', '', **options)
    assert broken['exception']['line'] == 2 and broken['trace_status'] == 'runtime_error'
    assert broken['steps'][-1]['function'] == 'f' and broken['steps'][-1]['variables']['x'] == '1'
    assert not any(s['event'] == 'return' for s in broken['steps'])
    recursive = run_trace_process('def f(x):\n    return f(x + 1)\nprint(f(0))', '', **options)
    assert recursive['truncated'] and recursive['truncation_reason'] == 'call_depth_limit'
    for text in ['x = [1] * 1000000', 'x = [1]\nx *= 1000000', 'x = []\nfor i in range(200):\n    x.append(i)']:
        limited = run_trace_process(text, '', **options)
        assert limited['truncated'] and limited['truncation_reason'] == 'list_limit'
    combined = run_trace_process('a = [1]\na += [2]\na[0] = 3\nprint(a)', '', **options)
    assert combined['steps'][-1]['stdout'] == '[3, 2]\n'
    for text in ['text = "a"\nx = text[0]\nprint(x * 1000000)', 'text = "a"\nfor x in text:\n    print(x * 1000000)']:
        limited = run_trace_process(text, '', **options)
        assert limited['truncation_reason'] == 'text_limit'
    for text in ['x = []\nx.__class__', 'def f(__x):\n    return __x', '@print\ndef f():\n    return 1', 'x = []\nx.append(x)', 'x = []\nx.extend([1])']:
        rejected = run_trace_process(text, '', **options)
        assert rejected['trace_status'] in {'unsupported', 'runtime_error'}


def test_remaining_lesson_apis_keep_unlock_and_no_writes(client, monkeypatch):
    from app.api import execution_trace
    from app.services.problem_catalog import LEVELS, PROBLEMS
    from test_learning_history import account
    headers = account(client, 'trace_twelve', '13800000404')
    body = {'problem_id': 'count-at-least-v1', 'code': PROBLEMS['count-at-least-v1'].reference_solution, 'stdin': '4\n60\n59\n60\n80\n100\n'}
    assert client.post('/api/v1/code/execution-trace', headers=headers, json=body).status_code == 403
    monkeypatch.setattr(execution_trace, 'passed_problem_ids', lambda db, user: {s.problem_id for s in LEVELS})
    for slot in LEVELS[4:]:
        lesson = PROBLEMS[slot.problem_id]
        sample = lesson.examples[0]
        response = client.post('/api/v1/code/execution-trace', headers=headers, json={
            'problem_id': lesson.problem_id, 'code': lesson.reference_solution, 'stdin': sample.stdin,
        })
        assert response.status_code == 200, (slot.id, response.text)
        result = response.json()['data']
        assert result['trace_status'] == 'completed' and result['steps'][-1]['stdout'] == sample.stdout, slot.id
    assert client.get('/api/v1/code/submissions', headers=headers).json()['data']['total'] == 0
