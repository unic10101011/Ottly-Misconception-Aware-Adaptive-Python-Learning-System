"""
安全检查模块
拦截危险代码和非法操作
"""
import ast
from typing import Tuple

# 危险模块黑名单
DANGEROUS_MODULES = {
    'os', 'sys', 'subprocess', 'shutil', 'socket', 'http', 'urllib', 
    'requests', 'ftplib', 'pickle', 'marshal', 'importlib', '__import__',
    'exec', 'eval', 'compile', 'globals', 'locals', 'vars', 'dir', 'id',
    'getattr', 'setattr', 'delattr', 'hasattr', 'open', 'file',
    'codeop', 'code', 'inspect', 'traceback', 'linecache', 'syslog',
    'logging', 'ctypes', 'cffi', 'gc', 'threading', 'multiprocessing',
    'queue', 'asyncio', 'concurrent', 'atexit', 'signal', 'timeit',
    'profile', 'pstats', 'hotshot', 'lsprof', 'py_compile', 'compileall',
    'dis', 'opcode', 'tokenize', 'token', 'keyword', 'parser', 'symtable',
    'ast', 'pdb', 'bdb', 'faulthandler', 'tracemalloc', 'resource'
}

# 游戏合法模块白名单
ALLOWED_MODULES = {
    'math', 'time',
}

# Only public operations needed by the introductory exercises are exposed.
# In particular, frame/generator attributes and str.format can traverse Python
# objects without spelling a forbidden attribute directly in the AST.
ALLOWED_ATTRIBUTES = {
    'append', 'extend', 'insert', 'pop', 'remove', 'clear', 'copy', 'count',
    'index', 'reverse', 'sort', 'keys', 'values', 'items', 'get', 'update',
    'setdefault', 'add', 'discard', 'union', 'intersection', 'difference',
    'split', 'rsplit', 'splitlines', 'join', 'strip', 'lstrip', 'rstrip',
    'replace', 'startswith', 'endswith', 'lower', 'upper', 'title',
    'capitalize', 'casefold', 'isdigit', 'isdecimal', 'isnumeric', 'isalpha',
    'isalnum', 'isspace', 'islower', 'isupper', 'isascii', 'find', 'rfind',
    'removeprefix', 'removesuffix', 'zfill',
    'sqrt', 'floor', 'ceil', 'fabs', 'factorial', 'gcd', 'lcm', 'isqrt',
    'sin', 'cos', 'tan', 'radians', 'degrees', 'log', 'log2', 'log10',
    'exp', 'pow', 'isfinite', 'isinf', 'isnan', 'pi', 'e', 'tau', 'inf', 'nan',
    'sleep', 'time', 'monotonic',
}

class SecurityChecker(ast.NodeVisitor):
    """AST安全检查器"""
    
    def __init__(self):
        self.errors = []
        self.has_errors = False
    
    def check_code(self, code: str) -> Tuple[bool, list]:
        """检查代码安全性"""
        self.errors = []
        self.has_errors = False
        
        try:
            tree = ast.parse(code)
            self.visit(tree)
        except SyntaxError as e:
            self.errors.append({
                'type': '语法错误',
                'line': e.lineno,
                'column': e.offset,
                'message': str(e),
                'suggestion': '请检查括号、引号是否配对，语句是否完整'
            })
            self.has_errors = True
        
        return not self.has_errors, self.errors
    
    def visit_Import(self, node):
        """检查import语句"""
        for name in node.names:
            module_name = name.name.split('.')[0]
            if module_name in DANGEROUS_MODULES:
                self.errors.append({
                    'type': '安全警告',
                    'line': node.lineno,
                    'column': node.col_offset,
                    'message': f'禁止导入危险模块: {name.name}',
                    'suggestion': '此模块可能会访问系统资源，建议使用游戏开发常用模块'
                })
                self.has_errors = True
            elif name.name not in ALLOWED_MODULES:
                self.errors.append({
                    'type': '安全警告',
                    'line': node.lineno,
                    'column': node.col_offset,
                    'message': f'不支持导入模块: {name.name}',
                    'suggestion': '当前教学执行器仅支持 math 和 time 模块'
                })
                self.has_errors = True
            if name.asname and name.asname.startswith('__'):
                self.reject(node, '不支持特殊模块别名')
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        """检查from...import语句"""
        if node.level or node.module not in ALLOWED_MODULES:
            self.reject(node, '只支持导入 math 和 time 教学模块')
        for alias in node.names:
            if (alias.name not in ALLOWED_ATTRIBUTES or
                    alias.asname and alias.asname.startswith('__')):
                self.reject(node, '不支持导入此模块成员')
        self.generic_visit(node)

    def reject(self, node, message):
        self.has_errors = True
        self.errors.append({'type': '安全警告', 'line': node.lineno,
                            'column': node.col_offset, 'message': message,
                            'suggestion': '请使用当前课程中的普通变量、函数和集合操作'})

    def visit_Name(self, node):
        if node.id.startswith('__') or node.id in {
                'getattr', 'setattr', 'delattr', 'hasattr', 'globals', 'locals',
                'vars', 'eval', 'exec', 'compile', 'open', 'help', 'dir'}:
            self.reject(node, '禁止访问特殊运行时名称或反射函数')

    def visit_arg(self, node):
        if node.arg.startswith('__'):
            self.reject(node, '不支持特殊参数名称')

    def visit_FunctionDef(self, node):
        if node.name.startswith('__') or node.decorator_list:
            self.reject(node, '不支持特殊函数名称或装饰器')
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.reject(node, '当前课程不支持自定义类型')

    def visit_MatchClass(self, node):
        self.reject(node, '当前课程不支持类型模式匹配')

    def visit_Attribute(self, node):
        """Allow teaching operations, not access to arbitrary runtime objects."""
        if node.attr not in ALLOWED_ATTRIBUTES:
            self.reject(node, f'不支持访问属性: {node.attr}')
        self.generic_visit(node)

    def visit_Call(self, node):
        """检查函数调用"""
        # 检查直接调用危险函数
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in DANGEROUS_MODULES:
                self.errors.append({
                    'type': '安全警告',
                    'line': node.lineno,
                    'column': node.col_offset,
                    'message': f'禁止调用危险函数: {func_name}()',
                    'suggestion': '此函数可能会执行危险操作，请使用安全的替代方案'
                })
                self.has_errors = True
        
        # 检查exec、eval等
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ['eval', 'exec', 'compile']:
                self.errors.append({
                    'type': '安全警告',
                    'line': node.lineno,
                    'column': node.col_offset,
                    'message': f'禁止动态执行代码: {func_name}()',
                    'suggestion': '动态执行代码会带来安全风险，请使用常规代码实现'
                })
                self.has_errors = True
        self.generic_visit(node)
    
    def visit_While(self, node):
        """检查while循环（可能的死循环）"""
        # 标记循环位置用于后续运行时检测
        self.generic_visit(node)
    
    def visit_For(self, node):
        """检查for循环"""
        self.generic_visit(node)
