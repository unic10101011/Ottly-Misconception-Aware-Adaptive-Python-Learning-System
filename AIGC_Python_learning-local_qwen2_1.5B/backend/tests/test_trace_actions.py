from app.services.sandbox.trace_runner import run_trace_process


def replay(code, stdin=''):
    return run_trace_process(code, stdin, supports_text=True, supports_structures=True)


def test_greeting_actions_use_completed_input_and_print_only():
    result = replay('friend = input()\nprint("Hello, " + friend + "!")', 'Ottly\n')
    first, read, printed = result['steps']
    assert first.get('action') is None
    assert read['stdout'] == ''
    assert read['action']['kind'] == 'input'
    assert read['action']['parts'] == ["'Ottly'"]
    assert read['action']['target'] == 'friend'
    assert printed['action']['kind'] == 'print'
    assert printed['action']['parts'] == ["'Hello, '", "'Ottly'", "'!'"]
    assert printed['action']['result'] == "'Hello, Ottly!'"
    assert printed['stdout'] == 'Hello, Ottly!\n'


def test_accumulation_and_replacement_are_distinct_and_rounds_are_real():
    code = 'total = 0\nfor i in range(1, 4):\n    total += i\nprint(total)'
    summed = replay(code)
    actions = [s['action'] for s in summed['steps'] if s.get('action', {}).get('kind') == 'add']
    assert [(a['parts'], a['result'], a['round']) for a in actions] == [(['0', '1'], '1', 1), (['1', '2'], '3', 2), (['3', '3'], '6', 3)]
    overwritten = replay(code.replace('total += i', 'total = i'))
    replace = [s['action'] for s in overwritten['steps'] if s.get('action', {}).get('kind') == 'replace']
    assert replace[1]['before'] == '1' and replace[1]['result'] == '2'
    assert replace[1]['round'] == 2
    assert '错误' not in str(replace)


def test_failed_complex_and_same_line_statements_do_not_invent_operations():
    failed = replay('friend = input()\nprint(friend + 1)', 'Ottly\n')
    assert failed['steps'][-1]['event'] == 'exception'
    assert failed['steps'][-1]['action']['kind'] == 'exception'
    complex_result = replay('a = 2\nb = a * 3\nprint(b)')
    assert not any(s.get('action', {}).get('kind') == 'add' for s in complex_result['steps'])
    same_line = replay('a = 1; b = 2\nprint(a + b)')
    assert same_line['trace_status'] == 'unsupported'
    assert same_line['steps'] == []


def test_function_scope_and_repeated_inputs_do_not_mix_evidence():
    result = replay('def f(x):\n    return x + 1\na = f(2)\nprint(a)')
    assert result['trace_status'] == 'completed'
    assert any(s.get('action', {}).get('kind') == 'return' for s in result['steps'])
    assert not any(s.get('action', {}).get('kind') == 'add' for s in result['steps'])
    two = replay('a = input()\nb = input()\nprint(a + b)', 'A\nB\n')
    assert [s['action']['parts'] for s in two['steps'] if s.get('action', {}).get('kind') == 'input'] == [["'A'"], ["'B'"]]


def test_nested_loop_rounds_restart_and_do_not_inherit_outer_round():
    result = replay('total = 0\nfor i in range(2):\n    for j in range(2):\n        total += 1\nprint(total)')
    additions = [s['action'] for s in result['steps'] if s.get('action', {}).get('kind') == 'add']
    entries = [s['action'] for s in result['steps'] if s.get('action', {}).get('kind') == 'loop' and s['action']['line'] == 3]
    assert [a['round'] for a in additions] == [1, 2, 1, 2]
    assert [a['round'] for a in entries] == [1, 2, 1, 2]


def test_caller_action_does_not_repeat_output_from_function():
    result = replay('def f():\n    print(1)\n    return 2\na = f()\nprint(a)')
    previous_stdout = ''
    for step in result['steps']:
        output = step.get('action', {}).get('output')
        if output:
            assert step['stdout'] == previous_stdout + output
        previous_stdout = step['stdout']
