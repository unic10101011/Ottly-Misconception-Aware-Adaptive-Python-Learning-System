"""Offline content acceptance: run from backend with any Python 3 interpreter."""
import ast
import json
from pathlib import Path
import subprocess
import sys


PRACTICE = Path(__file__).resolve().parents[1] / 'app' / 'data' / 'practice.json'


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
    case_count = 0
    for spec in specs:
        assert spec['source_url'].startswith('https://')
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
          f'{len(specs)} targeted wrong answers rejected, 3 direct function checks')


if __name__ == '__main__':
    main()
