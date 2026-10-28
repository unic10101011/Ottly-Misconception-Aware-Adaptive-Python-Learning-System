"""Conservative action evidence. Never evaluates user expressions or calls user code."""
import ast


def scalar_values(values):
    return {name: str(value) if isinstance(value, str) else value for name, value in values.items()
            if not name.startswith('__') and (type(value) in (int, bool, float) or isinstance(value, str))}


def additive_parts(node, values):
    if isinstance(node, ast.Constant) and type(node.value) in (str, int):
        return [node.value]
    if isinstance(node, ast.Name) and node.id in values and type(values[node.id]) in (str, int):
        return [values[node.id]]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = additive_parts(node.left, values), additive_parts(node.right, values)
        if left is not None and right is not None and len(left) + len(right) <= 8:
            parts = left + right
            if all(type(p) is type(parts[0]) for p in parts):
                return parts
    return None


def combined(parts):
    return ''.join(parts) if type(parts[0]) is str else sum(parts)


class ActionRecorder:
    def __init__(self, tree):
        self.statements = {}
        self.loops = []
        for node in ast.walk(tree):
            if isinstance(node, ast.stmt):
                self.statements.setdefault(node.lineno, []).append(node)
            if isinstance(node, (ast.For, ast.While)):
                self.loops.append(node)
        self.previous = {}
        self.last_scope = None
        self.last_stdout = ''
        self.rounds = {}

    def record(self, values, event, line, scope, stdout, reads, shown, return_value=None):
        current = scalar_values(values)
        old = self.previous.get(scope)
        action = None
        if event in ('exception', 'call', 'return'):
            action = {'kind': event, 'line': line}
            if event == 'return':
                action['result'] = return_value
        elif old and old['event'] == 'line':
            changes = [{'name': name, 'before': old['shown'].get(name, '未定义'), 'after': value}
                       for name, value in shown.items() if old['shown'].get(name) != value][:4]
            action = {'kind': 'change', 'line': old['line'], 'changes': changes}
            if stdout.startswith(self.last_stdout) and stdout != self.last_stdout:
                action['output'] = stdout[len(self.last_stdout):]
            # Cross-function gaps can contain arbitrary user calls: retain only
            # actual state changes instead of reconstructing an expression.
            nodes = self.statements.get(old['line'], [])
            node = nodes[0] if len(nodes) == 1 and self.last_scope == scope else None
            if isinstance(node, (ast.For, ast.While)):
                if event == 'line' and node.body[0].lineno <= line <= node.body[-1].end_lineno:
                    key = (scope, node.lineno)
                    self.rounds[key] = self.rounds.get(key, 0) + 1
                    action.update(kind='loop', round=self.rounds[key])
                    for inner in self.loops:
                        if node.body[0].lineno <= inner.lineno <= node.body[-1].end_lineno:
                            self.rounds[(scope, inner.lineno)] = 0
            elif node and node.end_lineno == node.lineno:
                specific = self.statement_action(node, old, current, stdout, reads)
                if specific:
                    action.update(specific)
            containing = [n for n in self.loops if n.body[0].lineno <= old['line'] <= n.body[-1].end_lineno]
            if containing and action['kind'] != 'loop':
                loop = max(containing, key=lambda n: n.lineno)
                if (scope, loop.lineno) in self.rounds:
                    action['round'] = self.rounds[(scope, loop.lineno)]
        self.previous[scope] = {'event': event, 'line': line, 'values': current,
                                'shown': dict(shown), 'stdout': stdout, 'reads': len(reads)}
        self.last_scope = scope
        self.last_stdout = stdout
        return action

    @staticmethod
    def statement_action(node, old, current, stdout, reads):
        before = old['values']
        target = node.targets[0].id if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) else None
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
        if target and target in current:
            value = node.value
            result = current[target]
            data = {'target': target, 'result': repr(result), 'before': repr(before[target]) if target in before else '未定义'}
            new_reads = reads[old['reads']:]
            if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == 'input'
                    and not value.args and not value.keywords and len(new_reads) == 1 and result == new_reads[0]):
                return {**data, 'kind': 'input', 'parts': [repr(new_reads[0])]}
            parts = additive_parts(value, before)
            if isinstance(node, ast.AugAssign):
                if not isinstance(node.op, ast.Add) or target not in before or parts is None:
                    return None
                parts = [before[target], *parts]
                if not all(type(p) is type(parts[0]) for p in parts) or type(parts[0]) not in (str, int):
                    return None
            if parts is not None and type(result) is type(parts[0]) and combined(parts) == result:
                if len(parts) > 1:
                    return {**data, 'kind': 'concat' if type(result) is str else 'add', 'parts': [repr(p) for p in parts]}
                return {**data, 'kind': 'replace' if target in before else 'assign', 'parts': [repr(p) for p in parts]}
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (isinstance(call.func, ast.Name) and call.func.id == 'print' and len(call.args) == 1
                    and not call.keywords and stdout.startswith(old['stdout'])):
                parts = additive_parts(call.args[0], before)
                if parts is not None:
                    result = combined(parts)
                    if stdout[len(old['stdout']):] == str(result) + '\n':
                        return {'kind': 'print', 'parts': [repr(p) for p in parts], 'result': repr(result),
                                'output': str(result) + '\n'}
        return None
