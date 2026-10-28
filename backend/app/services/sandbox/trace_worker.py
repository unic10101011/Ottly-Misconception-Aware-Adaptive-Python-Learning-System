"""Bounded teaching trace for the twelve lessons. Runs only in a child process."""
import ast
from contextlib import redirect_stdout
import io
import json
import sys
import time
from types import FunctionType

from .security_check import SecurityChecker
from .trace_actions import ActionRecorder

FILENAME = '<ottly-trace>'
STEP_LIMIT = 300
OUTPUT_LIMIT = 6000
TEXT_LIMIT = 2000
LIST_LIMIT = 100
CALL_DEPTH_LIMIT = 16


class TraceLimit(Exception):
    pass


class BoundedText(str):
    def __new__(cls, value):
        if len(value) > TEXT_LIMIT:
            raise TraceLimit('text_limit')
        return super().__new__(cls, value)

    def __add__(self, other):
        if not isinstance(other, str):
            return NotImplemented
        return BoundedText(super().__add__(other))

    def __radd__(self, other):
        if not isinstance(other, str):
            return NotImplemented
        return BoundedText(str.__add__(other, self))

    def __mul__(self, count):
        if not isinstance(count, int):
            return NotImplemented
        if len(self) * max(0, count) > TEXT_LIMIT:
            raise TraceLimit('text_limit')
        return BoundedText(super().__mul__(count))

    __rmul__ = __mul__

    def __mod__(self, other):
        raise TypeError('首版回放暂不支持字符串%格式化。')

    def __getitem__(self, index):
        return BoundedText(super().__getitem__(index))

    def __iter__(self):
        return (BoundedText(char) for char in super().__iter__())


class TextConstants(ast.NodeTransformer):
    def visit_Constant(self, node):
        if type(node.value) is str:
            return ast.copy_location(ast.Call(func=ast.Name(id='__trace_text__', ctx=ast.Load()), args=[node], keywords=[]), node)
        return node

    def visit_List(self, node):
        if isinstance(node.ctx, ast.Load):
            self.generic_visit(node)
            return ast.copy_location(ast.Call(func=ast.Name(id='__trace_list__', ctx=ast.Load()), args=[node], keywords=[]), node)
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Attribute):
            return ast.copy_location(ast.Call(func=ast.Name(id='__trace_append__', ctx=ast.Load()),
                                              args=[node.func.value, *node.args], keywords=[]), node)
        return node


def checked_item(value):
    if type(value) not in (int, bool, float, str, BoundedText):
        raise TypeError('回放仅支持一维数值或文字列表。')
    if type(value) is int and value.bit_length() > 4096:
        raise TraceLimit('integer_limit')
    if isinstance(value, str) and len(value) > TEXT_LIMIT:
        raise TraceLimit('text_limit')
    return BoundedText(value) if isinstance(value, str) else value


class BoundedList(list):
    def __init__(self, values):
        if len(values) > LIST_LIMIT:
            raise TraceLimit('list_limit')
        super().__init__(checked_item(value) for value in values)

    def append(self, value):
        if len(self) >= LIST_LIMIT:
            raise TraceLimit('list_limit')
        super().append(checked_item(value))

    def __setitem__(self, index, value):
        super().__setitem__(index, checked_item(value))

    def __mul__(self, count):
        if not isinstance(count, int):
            return NotImplemented
        if len(self) * max(0, count) > LIST_LIMIT:
            raise TraceLimit('list_limit')
        return BoundedList(super().__mul__(count))

    __rmul__ = __mul__

    def __add__(self, other):
        if not isinstance(other, BoundedList):
            return NotImplemented
        return BoundedList(super().__add__(other))

    def __iadd__(self, other):
        result = self + other
        list.__setitem__(self, slice(None), result)
        return self

    def __imul__(self, count):
        result = self * count
        # Bypass the scalar-only item setter for this bounded internal replacement.
        list.__setitem__(self, slice(None), result)
        return self


def bounded_append(value, item):
    if not isinstance(value, BoundedList):
        raise TypeError('append只能用于列表。')
    value.append(item)


class TraceOutput(io.StringIO):
    def write(self, value):
        remaining = OUTPUT_LIMIT - self.tell()
        super().write(value[:remaining])
        if len(value) > remaining:
            raise TraceLimit('output_limit')
        return len(value)


def validate(tree, supports_text=False, supports_structures=False):
    allowed = (ast.Module, ast.Assign, ast.AugAssign, ast.For, ast.While, ast.If, ast.Expr,
               ast.Name, ast.Load, ast.Store, ast.Constant, ast.Call, ast.BinOp, ast.UnaryOp,
               ast.Compare, ast.BoolOp, ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod,
               ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt,
               ast.LtE, ast.Gt, ast.GtE, ast.Pass, ast.Break, ast.Continue) + ((ast.Div,) if supports_text else ())
    if supports_structures:
        allowed += (ast.List, ast.Subscript, ast.Attribute, ast.FunctionDef, ast.arguments, ast.arg, ast.Return)
    nodes = list(ast.walk(tree))
    if len(nodes) > 500:
        return '代码结构过大，请缩小后回放。'
    parents = {child: node for node in nodes for child in ast.iter_child_nodes(node)}
    builtins = {'input', 'int', 'print', 'range', 'len'}
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)} if supports_structures else set()
    if len(functions) > 8:
        return '回放最多支持8个普通函数。'
    statement_lines = [node.lineno for node in nodes if isinstance(node, ast.stmt)]
    if len(statement_lines) != len(set(statement_lines)):
        return '首版回放请将每条语句分别写在单独一行，循环和条件的正文也需要换行。'
    for node in nodes:
        if not isinstance(node, allowed):
            return '回放支持当前教学语法；暂不支持导入、任意属性、复杂容器或其他高级语法。'
        if isinstance(node, ast.Constant):
            if supports_text and type(node.value) is str:
                if len(node.value) > TEXT_LIMIT:
                    return '字符串常量过长，请缩小后回放。'
            elif supports_structures and node.value is None:
                pass
            elif type(node.value) not in ((int, bool, float) if supports_text else (int, bool)) or abs(node.value) > 1000000:
                return '数值常量绝对值不能超过1000000；第8关仅支持整数常量。'
        if isinstance(node, ast.Name) and ('__' in node.id or isinstance(node.ctx, ast.Store) and node.id in builtins):
            return '回放暂不支持特殊变量名或覆盖内置函数名。'
        if isinstance(node, ast.FunctionDef):
            if node not in tree.body or '__' in node.name or node.name in builtins or node.decorator_list or node.returns:
                return '仅支持顶层普通函数，不支持嵌套、装饰器或特殊名称。'
            args = node.args
            if args.posonlyargs or args.vararg or args.kwarg or args.kwonlyargs or args.defaults or any(a.annotation for a in args.args):
                return '回放函数仅支持普通位置参数。'
        if isinstance(node, ast.arg) and ('__' in node.arg or node.arg in builtins):
            return '函数参数不能使用特殊名称或覆盖内置函数。'
        if isinstance(node, ast.Attribute):
            parent = parents.get(node)
            if node.attr != 'append' or not isinstance(parent, ast.Call) or parent.func is not node or not isinstance(node.value, ast.Name):
                return '回放仅支持列表变量.append，不支持其他属性访问。'
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and supports_structures:
                if len(node.args) != 1 or node.keywords:
                    return 'append需要一个普通参数。'
                continue
            calls = {'input', 'int', 'print', 'range'} | ({'len'} if supports_text else set()) | functions
            if not isinstance(node.func, ast.Name) or node.func.id not in calls or node.keywords:
                return '仅支持int、input、print、range、len及代码中定义的普通函数，不支持关键字参数。'
            if node.func.id == 'input':
                parent = parents.get(node)
                if supports_text:
                    if len(node.args) > 1:
                        return 'input最多接受一个提示参数。'
                elif node.args or not isinstance(parent, ast.Call) or not isinstance(parent.func, ast.Name) or parent.func.id != 'int':
                    return '第8关回放请使用int(input())读取整数。'
    return None


def main():
    protocol = sys.stdout
    wire_size = 0

    def emit(message):
        nonlocal wire_size
        line = json.dumps(message, ensure_ascii=False) + '\n'
        wire_size += len(line.encode('utf-8'))
        if wire_size > 2_000_000 and message['kind'] == 'step':
            raise TraceLimit('trace_size_limit')
        protocol.write(line)
        protocol.flush()

    def finish(status, *, exception=None, reason=None):
        emit({'kind': 'result', 'trace_status': status, 'exception': exception,
              'truncated': status in {'truncated', 'timeout'}, 'truncation_reason': reason})

    request = json.load(sys.stdin)
    code = request['code']
    supports_text = request.get('supports_text', False)
    supports_structures = request.get('supports_structures', False)
    # Defence in depth on Linux; the parent also has a wall-clock deadline.
    from .limits import apply_worker_limits
    apply_worker_limits(2)
    try:
        tree = ast.parse(code, filename=FILENAME)
        compiled = compile(tree, FILENAME, 'exec')
    except SyntaxError as error:
        finish('syntax_error', exception={'type': 'SyntaxError', 'message': error.msg, 'line': error.lineno, 'column': error.offset})
        return
    unsupported = validate(tree, supports_text, supports_structures)
    safe, errors = SecurityChecker().check_code(code)
    if unsupported or not safe:
        finish('unsupported', exception={'type': 'UnsupportedSyntax', 'message': unsupported or errors[0]['message'], 'line': None})
        return
    action_recorder = ActionRecorder(ast.parse(code, filename=FILENAME))
    if supports_text or supports_structures:
        # Only mark direct reads. A nested subscript may be skipped by short
        # circuit evaluation or an earlier exception on the same source line.
        original_subscripts = []
        for statement in ast.walk(tree):
            value = statement.value if isinstance(statement, (ast.Assign, ast.Expr)) else None
            if (isinstance(statement, ast.Expr) and isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name) and value.func.id == 'print'
                    and len(value.args) == 1 and not value.keywords):
                value = value.args[0]
            if isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name):
                original_subscripts.append(value)
        tree = ast.fix_missing_locations(TextConstants().visit(tree))
        compiled = compile(tree, FILENAME, 'exec')
    else:
        original_subscripts = []
    output = TraceOutput()
    inputs = io.StringIO(request['stdin'])
    started = time.monotonic()
    count = 0
    previous = {}
    frame_infos = {}
    frame_stacks = {}
    active_calls = []
    failed_frames = set()
    call_count = 0
    input_reads = []

    def read_input(prompt=''):
        if prompt:
            output.write(str(prompt))
        line = inputs.readline()
        if not line:
            raise EOFError('演示输入已用完，每次input需要一行。')
        value = line.rstrip('\n').removesuffix('\r')
        input_reads.append(value)
        return BoundedText(value) if supports_text else value

    def bounded_range(*args):
        value = range(*args)
        try:
            size = len(value)
        except OverflowError:
            raise TraceLimit('range_limit') from None
        if size > 10000:
            raise TraceLimit('range_limit')
        return value

    namespace = {'__builtins__': {'int': int, 'input': read_input, 'print': print, 'range': bounded_range}}
    if supports_text:
        namespace['__trace_text__'] = BoundedText
        namespace['__builtins__']['len'] = len
    if supports_structures:
        namespace.update(__trace_list__=BoundedList, __trace_append__=bounded_append)

    def describe(value):
        if type(value) is int and value.bit_length() > 4096:
            raise TraceLimit('integer_limit')
        if isinstance(value, BoundedList):
            return '[' + ', '.join(describe(item) for item in value) + ']'
        if isinstance(value, str):
            if len(value) > TEXT_LIMIT:
                raise TraceLimit('text_limit')
            shown = repr(value)
        elif type(value) in (int, bool, float) or value is None:
            shown = repr(value)
        elif type(value) is range:
            shown = '<range>'
        elif isinstance(value, FunctionType):
            shown = f'<函数 {value.__name__}>'
        else:
            shown = '<未展示的类型>'
        return shown[:160] + ('…' if len(shown) > 160 else '')

    def snapshot(values, event, line, exception=None, info=None, return_value=None, stack=None):
        nonlocal count, previous
        if count >= STEP_LIMIT:
            raise TraceLimit('step_limit')
        if time.monotonic() - started > 1.5:
            raise TraceLimit('wall_time_limit')
        variables = {}
        visual_values = {}
        for name, value in values.items():
            if name.startswith('__'):
                continue
            if len(variables) >= 32:
                raise TraceLimit('variable_limit')
            variables[name] = describe(value)
            if type(value) in (int, float):
                visual_values[name] = {'kind': 'number', 'text': variables[name]}
            elif isinstance(value, BoundedList):
                visual_values[name] = {'kind': 'list', 'items': [describe(item) for item in value]}
        accesses = []
        if event == 'line':
            for node in original_subscripts:
                if node.lineno != line:
                    continue
                target = values.get(node.value.id)
                index = node.slice.value if isinstance(node.slice, ast.Constant) else values.get(node.slice.id) if isinstance(node.slice, ast.Name) else None
                if isinstance(target, BoundedList) and type(index) is int and -len(target) <= index < len(target):
                    accesses.append({'name': node.value.id, 'index': index % len(target), 'mode': 'read' if isinstance(node.ctx, ast.Load) else 'write'})
        count += 1
        info = info or {'function': '<module>', 'scope_id': 'module'}
        old = previous.get(info['scope_id'], {})
        action = action_recorder.record(values, event, line, info['scope_id'], output.getvalue(), input_reads,
                                        variables, describe(return_value) if event == 'return' else None)
        emit({'kind': 'step', 'step': count, 'event': event, 'line': line, **info, 'variables': variables,
              **({'action': action} if action else {}),
              'visual_values': visual_values, 'list_accesses': accesses,
              'changed_variables': [name for name in variables if variables[name] != old.get(name)],
              'call_stack': [{'function': '<module>', 'scope_id': 'module'}, *(stack if stack is not None else [entry[1] for entry in active_calls])],
              'return_value': describe(return_value) if event == 'return' else None,
              'stdout': output.getvalue(), 'exception': exception})
        previous[info['scope_id']] = variables

    def trace(frame, event, arg):
        nonlocal call_count
        if frame.f_code.co_filename != FILENAME:
            return trace
        key = id(frame)
        if event == 'call' and frame.f_code.co_name != '<module>':
            if len(active_calls) >= CALL_DEPTH_LIMIT:
                raise TraceLimit('call_depth_limit')
            call_count += 1
            info = {'function': frame.f_code.co_name, 'scope_id': f'call-{call_count}'}
            frame_infos[key] = info
            failed_frames.discard(key)
            active_calls.append((key, info))
            frame_stacks[key] = [entry[1] for entry in active_calls]
            snapshot(frame.f_locals, 'call', frame.f_lineno, info=info)
        elif event == 'line' and frame.f_lineno > 0:
            snapshot(frame.f_locals, 'line', frame.f_lineno, info=frame_infos.get(key))
        elif event == 'exception':
            failed_frames.add(key)
        elif event == 'return' and frame.f_code.co_name != '<module>':
            if key not in failed_frames:
                snapshot(frame.f_locals, 'return', frame.f_lineno, info=frame_infos.get(key), return_value=arg)
            if active_calls and active_calls[-1][0] == key:
                active_calls.pop()
        return trace

    try:
        with redirect_stdout(output):
            sys.settrace(trace)
            try:
                exec(compiled, namespace, namespace)
            finally:
                sys.settrace(None)
        snapshot(namespace, 'end', None)
        finish('completed')
    except TraceLimit as error:
        finish('timeout' if str(error) == 'wall_time_limit' else 'truncated', reason=str(error))
    except Exception as error:
        sys.settrace(None)
        line = None
        error_frame = None
        tb = error.__traceback__
        while tb:
            if tb.tb_frame.f_code.co_filename == FILENAME:
                line = tb.tb_lineno
                error_frame = tb.tb_frame
            tb = tb.tb_next
        exception = {'type': type(error).__name__, 'message': str(error)[:300], 'line': line}
        try:
            snapshot(error_frame.f_locals if error_frame else namespace, 'exception', line, exception,
                     info=frame_infos.get(id(error_frame)) if error_frame else None,
                     stack=frame_stacks.get(id(error_frame)) if error_frame else None)
        except TraceLimit as limit:
            finish('truncated', exception=exception, reason=str(limit))
            return
        finish('runtime_error', exception=exception)


if __name__ == '__main__':
    main()
