"""Verify the reviewed curriculum examples, not arbitrary student programs.

Run from any directory with Python 3. This is an offline content check, not
the application's judge or a security sandbox. No third-party packages needed.
"""

import ast
import contextlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys


DOCUMENT = Path(__file__).with_name("03-12关题库选型与教学详解.md")
CASE_PATTERN = re.compile(
    r'^\| (公开|隐藏) \| `("(?:[^"\\]|\\.)*")`'
    r' \| `("(?:[^"\\]|\\.)*")` \|',
    re.MULTILINE,
)

# A targeted incorrect variant for each reviewed reference solution.
MUTATIONS = {
    1: ('Hello, World!', 'Hello, world!'),
    2: ('name + "!"', '"name" + "!"'),
    3: ('price * quantity', 'price + quantity'),
    4: ('n // k', 'n / k'),
    5: ('score >= 60', 'score > 60'),
    6: (' and ', ' or '),
    7: ('range(1, n + 1)', 'range(1, n)'),
    8: ('total = total + i', 'total = i'),
    9: ('saved < target', 'saved <= target'),
    10: ('count = count + 1', 'count = 1'),
    11: ('largest = values[0]', 'largest = 0'),
    12: ('return count', 'print(count)'),
}


def normalize(text):
    return text.replace('\r\n', '\n')


def run_example(code, stdin):
    return subprocess.run(
        [sys.executable, '-I', '-X', 'utf8', '-c', code],
        input=stdin,
        text=True,
        encoding='utf-8',
        capture_output=True,
        timeout=5,
        check=False,
    )


def check_function(code):
    functions = [
        node for node in ast.parse(code).body
        if isinstance(node, ast.FunctionDef) and node.name == 'count_at_least'
    ]
    assert len(functions) == 1, 'Expected count_at_least definition'
    namespace = {}
    module = ast.Module(body=functions, type_ignores=[])
    exec(compile(module, str(DOCUMENT), 'exec'), namespace)
    examples = [
        ([59, 60, 80, 100], 60, 3),
        ([], 60, 0),
        ([0, 99, 99], 100, 0),
        ([0, 50, 100], 0, 3),
        ([60], 60, 1),
    ]
    # The same function object is called repeatedly to catch leaked state.
    for scores, threshold, expected in examples:
        original = scores.copy()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = namespace['count_at_least'](scores, threshold)
        assert type(result) is int, 'Return must be int, not None or bool'
        assert result == expected, (scores, threshold, result, expected)
        assert scores == original, 'Function modified its input'
        assert output.getvalue() == '', 'Function printed instead of returning'
    return len(examples)


def main():
    document = DOCUMENT.read_text(encoding='utf-8')
    sections = re.split(r'^## 第 (\d{2}) 关[^\n]*\n', document, flags=re.MULTILINE)
    numbers = [int(number) for number in sections[1::2]]
    assert numbers == list(range(1, 13)), numbers
    passed_cases = 0
    rejected_mutations = 0
    function_checks = 0
    for level, section in zip(numbers, sections[2::2]):
        solutions = re.findall(r'^\*\*参考解：\*\*\s*```python\n(.*?)^```', section, re.MULTILINE | re.DOTALL)
        assert len(solutions) == 1, f'Level {level}: expected one reference solution'
        solution = solutions[0]
        cases = [
            (json.loads(stdin), json.loads(expected))
            for _, stdin, expected in CASE_PATTERN.findall(section)
        ]
        assert len(cases) == (1 if level == 1 else 7 if level == 5 else 4)
        for index, (stdin, expected) in enumerate(cases, 1):
            result = run_example(solution, stdin)
            assert result.returncode == 0, f'Level {level}, case {index}: {result.stderr}'
            assert normalize(result.stdout) == expected, (
                f'Level {level}, case {index}: {result.stdout!r} != {expected!r}'
            )
            passed_cases += 1
        before, after = MUTATIONS[level]
        assert solution.count(before) == 1, f'Level {level}: ambiguous mutation'
        wrong_solution = solution.replace(before, after, 1)
        for stdin, expected in cases:
            result = run_example(wrong_solution, stdin)
            if result.returncode != 0 or normalize(result.stdout) != expected:
                rejected_mutations += 1
                break
        else:
            raise AssertionError(f'Level {level}: all cases accepted the wrong solution')
        if level == 12:
            function_checks = check_function(solution)
        print(f'Level {level:02d}: {len(cases)} cases passed; incorrect variant rejected')
    print(
        f'PASS: {len(numbers)} levels, {passed_cases} reference cases, '
        f'{rejected_mutations} incorrect variants rejected, '
        f'{function_checks} direct function checks; Python {sys.version.split()[0]}'
    )


if __name__ == '__main__':
    main()
