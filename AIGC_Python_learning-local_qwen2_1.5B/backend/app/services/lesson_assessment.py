"""Server-owned teaching requirements, separate from model input and run mode."""
import ast
import copy


def requirement_error(lesson, code: str) -> dict | None:
    mode = getattr(lesson, 'assessment', 'output')
    if mode == 'output':
        return None
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None  # The normal sandbox reports the original syntax error.
    message = None
    if mode == 'list_maximum':
        nodes = list(ast.walk(tree))
        forbidden = next((node for node in nodes
                          if (isinstance(node, ast.Name) and node.id in {'max', 'sorted'})
                          or (isinstance(node, ast.Attribute) and node.attr == 'sort')), None)
        if forbidden is not None:
            message = '本关请通过比较更新最大值，不使用 max、sorted 或 sort。'
        elif not any(isinstance(node, ast.For) for node in nodes) or not any(
                isinstance(node, ast.List) or (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == 'list') for node in nodes):
            message = '本关请先用列表保存记录，再使用 for 循环逐个比较。'
    elif mode in {'count_at_least', 'practice_function'}:
        reference = ast.parse(lesson.starter_code)
        function_name = ('count_at_least' if mode == 'count_at_least'
                         else lesson.direct_function_tests[0].function_name)

        def frame(module):
            module = copy.deepcopy(module)
            for node in module.body:
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    node.body = [ast.Pass()]
            return ast.dump(module, include_attributes=False)

        if frame(tree) != frame(reference):
            message = f'请仅补全 {function_name} 的函数体，保留函数签名和下方已提供的输入输出代码。'
    if message:
        return {'success': False, 'output': '', 'output_available': False,
                'errors': [{'type': 'RequirementError', 'line': None, 'message': message}],
                'execution_time': 0.0}
    return None


def function_test_program(code: str, test) -> tuple[str, str]:
    """Run fresh function definitions, then several calls in the same process.

    Hidden expectations remain server-owned. Every observed True/False is
    produced by the sandbox, never fabricated as a learner's stdout.
    """
    tree = ast.parse(code)
    definition = next(node for node in tree.body
                      if isinstance(node, ast.FunctionDef) and node.name == 'count_at_least')
    lines = [ast.unparse(definition)]
    for call in test.calls:
        lines.extend([
            f'_lesson_scores = {call.scores!r}',
            '_lesson_before = list(_lesson_scores)',
            f'_lesson_result = count_at_least(_lesson_scores, {call.threshold!r})',
            f'print(type(_lesson_result) is int and _lesson_result == {call.expected!r} '
            'and _lesson_scores == _lesson_before)',
        ])
    return '\n'.join(lines) + '\n', 'True\n' * len(test.calls)


def direct_function_test_program(code: str, test) -> tuple[str, str]:
    tree = ast.parse(code)
    definition = next(node for node in tree.body
                      if isinstance(node, ast.FunctionDef) and node.name == test.function_name)
    lines = ['def _practice_check():', '    _practice_print = print']
    lines.extend('    ' + line for line in ast.unparse(definition).splitlines())
    for call in test.calls:
        args = ', '.join(repr(value) for value in call.args)
        lines.append(f'    _practice_result = {test.function_name}({args})')
        lines.append(f'    _practice_print(type(_practice_result) is {type(call.expected).__name__} '
                     f'and _practice_result == {call.expected!r})')
    lines.append('_practice_check()')
    return '\n'.join(lines) + '\n', 'True\n' * len(test.calls)
