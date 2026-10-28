"""Offline content acceptance: run from backend with any Python 3 interpreter."""
import ast
import copy
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit


PRACTICE = Path(__file__).resolve().parents[1] / 'app' / 'data' / 'practice.json'
sys.path.insert(0, str(PRACTICE.parents[2]))
from app.services.misconceptions import MISCONCEPTION_TAGS

FULL_PRACTICE_MISTAKES = {
    'practice-03-4-v1': ('(length + width) * 2', 'length + width * 2'),
    'practice-03-5-v1': ('before - given', 'given - before'),
    'practice-03-6-v1': ('per_group * groups', 'children + teachers * groups'),
    'practice-04-4-v1': ('remaining // 60', 'total_seconds // 60'),
    'practice-04-5-v1': ('number // 10 % 10', 'number // 10'),
    'practice-04-6-v1': ('(number - 1) % seats_per_row + 1', 'number % seats_per_row'),
    'practice-05-4-v1': ('ottly_count > friend_count', 'ottly_count >= friend_count'),
    'practice-05-5-v1': ('height <= 100', 'height < 100'),
    'practice-05-6-v1': ('print(current - target)', 'print(target - current)'),
    'practice-06-4-v1': ('hour < 18', 'hour <= 18'),
    'practice-06-5-v1': ('left == 1 and right == 0', 'left == 1'),
    'practice-06-6-v1': ('and not sale == 1', ''),
    'practice-07-4-v1': ('range(n, -1, -1)', 'range(n, 0, -1)'),
    'practice-07-5-v1': ('first + i * step', 'first + (i + 1) * step'),
    'practice-07-6-v1': ('weight > 0 and weight <= limit', 'weight <= limit'),
    'practice-08-4-v1': ('expense = expense - change', 'expense = expense + change'),
    'practice-08-5-v1': ('10 + (distance - 5) * 3', 'distance * 3'),
    'practice-08-6-v1': ('    else:\n        streak = 0', '    else:\n        total = 0'),
    'practice-09-4-v1': ('count = 0', 'count = 1'),
    'practice-09-5-v1': ('print(a)', 'print(b)'),
    'practice-09-6-v1': ('while n != 1:', 'while n > 2:'),
    'practice-10-4-v1': ('char != "#"', 'char != "#" and char != " "'),
    'practice-10-5-v1': ('    previous = char', '    previous = ""'),
    'practice-10-6-v1': ('backward = char + backward', 'backward = backward + char'),
    'practice-11-4-v1': ('range(n - 1, -1, -1)', 'range(n - 1, 0, -1)'),
    'practice-11-5-v1': ('values[i] - values[i - 1]', 'values[i - 1] - values[i]'),
    'practice-11-6-v1': ('(i + k) % n', '(i - k) % n'),
    'practice-12-4-v1': ('return low', 'return high'),
    'practice-12-5-v1': ('return longest', 'return current'),
    'practice-12-6-v1': ('values[i] <= values[i - 1]', 'values[i] < values[i - 1]'),
}


def validate_metadata(spec):
    problem_id = spec['problem_id']
    assert type(spec.get('difficulty')) is int and spec['difficulty'] in {1, 2, 3}, f'{problem_id}: difficulty'
    tags = spec.get('target_misconception_tags', [])
    assert isinstance(tags, list) and 1 <= len(tags) <= 2, f'{problem_id}: target_misconception_tags'
    assert all(isinstance(tag, str) and tag in MISCONCEPTION_TAGS for tag in tags), f'{problem_id}: unknown tag'
    assert len(tags) == len(set(tags)), f'{problem_id}: duplicate tags'
    source = spec.get('source_url')
    assert isinstance(source, str), f'{problem_id}: source_url'
    parsed = urlsplit(source)
    assert parsed.scheme == 'https' and parsed.netloc and not any(c.isspace() for c in source), f'{problem_id}: source_url'


def run(code, stdin):
    return subprocess.run(
        [sys.executable, '-I', '-X', 'utf8', '-c', code], input=stdin,
        text=True, capture_output=True, encoding='utf-8', timeout=4, check=False,
    )


def check_function(spec):
    tree = ast.parse(spec['reference_solution'])
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert len(functions) == 1, spec['problem_id']
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(PRACTICE), 'exec'), namespace)
    function = namespace[functions[0].name]
    if spec['level_no'] != 12:
        return
    if spec.get('direct_function_tests'):
        for test in spec['direct_function_tests']:
            for call in test['calls']:
                result = namespace[test['function_name']](*copy.deepcopy(call['args']))
                assert type(result) is type(call['expected']) and result == call['expected'], spec['problem_id']
        return
    if functions[0].name == 'greet':
        assert function('Mia') == 'Hi, Mia'
        assert function('Bo') == 'Hi, Bo'
    elif functions[0].name == 'can_sail':
        assert function(5, 2) is True
        assert function(6, 2) is False
        assert function(5, 3) is False
    elif functions[0].name == 'count_passed':
        scores = [59, 60, 80, 60]
        assert type(function(scores, 60)) is int and function(scores, 60) == 3
        assert scores == [59, 60, 80, 60]
        assert function([], 60) == 0
        assert function([100, 0], 100) == 1
    else:
        raise AssertionError(f"Unknown practice function: {functions[0].name}")


def main():
    specs = json.loads(PRACTICE.read_text(encoding='utf-8'))
    assert len(specs) == 36
    assert len({spec['problem_id'] for spec in specs}) == 36
    for level in range(1, 13):
        assert len([spec for spec in specs if spec['level_no'] == level]) == 3
    for path in sorted(PRACTICE.parent.glob('practice-*.json')):
        spec = json.loads(path.read_text(encoding='utf-8'))
        before, after = FULL_PRACTICE_MISTAKES[spec['problem_id']]
        assert before in spec['reference_solution'], spec['problem_id']
        cases = [{'stdin': case['stdin'], 'stdout': case['expected_output']} for case in spec['tests']]
        specs.append({**spec, 'sample': cases[0], 'hidden': cases[1:],
                      'wrong_solution': spec['reference_solution'].replace(before, after, 1)})
    assert len(specs) == 66
    case_count = 0
    for spec in specs:
        validate_metadata(spec)
        cases = [spec['sample'], *spec['hidden']]
        wrong_rejected = False
        for case in cases:
            reference = run(spec['reference_solution'], case['stdin'])
            assert reference.returncode == 0, (spec['problem_id'], reference.stderr)
            assert reference.stdout == case['stdout'], (spec['problem_id'], case, reference.stdout)
            wrong = run(spec['wrong_solution'], case['stdin'])
            wrong_rejected |= wrong.returncode != 0 or wrong.stdout != case['stdout']
            case_count += 1
        assert wrong_rejected, f"Targeted wrong answer was accepted: {spec['problem_id']}"
        if spec['level_no'] == 12:
            check_function(spec)
    print(f'PASS: {len(specs)} practice questions, {case_count} reference cases, '
          f'{len(specs)} targeted wrong answers rejected, 6 function exercises checked')


if __name__ == '__main__':
    main()
