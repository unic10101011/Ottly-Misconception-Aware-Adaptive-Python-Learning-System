"""
安全检查模块
拦截危险代码和非法操作
"""
import ast
import builtins
from typing import Tuple, Optional

# 危险模块黑名单
DANGEROUS_MODULES = {
    'os', 'sys', 'subprocess', 'shutil', 'socket', 'http', 'urllib', 
    'requests', 'ftplib', 'pickle', 'marshal', 'importlib', '__import__',
    'exec', 'eval', 'compile', 'globals', 'locals', 'vars', 'dir', 'id',
    'getattr', 'setattr', 'delattr', 'hasattr', 'open', 'file', 'input',
    'codeop', 'code', 'inspect', 'traceback', 'linecache', 'syslog',
    'logging', 'ctypes', 'cffi', 'gc', 'threading', 'multiprocessing',
    'queue', 'asyncio', 'concurrent', 'atexit', 'signal', 'timeit',
    'profile', 'pstats', 'hotshot', 'lsprof', 'py_compile', 'compileall',
    'dis', 'opcode', 'tokenize', 'token', 'keyword', 'parser', 'symtable',
    'ast', 'pdb', 'bdb', 'faulthandler', 'tracemalloc', 'resource'
}

# 游戏合法模块白名单
ALLOWED_MODULES = {
    'math', 'random', 'time', 'datetime', 'collections', 'itertools',
    'functools', 'operator', 're', 'string', 'struct', 'array', 'heapq',
    'bisect', 'queue', 'deque', 'Counter', 'defaultdict', 'OrderedDict',
    'namedtuple', 'enum', 'dataclasses', 'typing', 'copy', 'pprint',
    'turtle', 'pygame', 'pygame.locals'  # 游戏开发库
}

# 危险属性黑名单
DANGEROUS_ATTRIBUTES = {
    '__import__', '__eval__', '__exec__', '__globals__', '__locals__',
    '__builtins__', '__code__', '__dict__', '__class__', '__base__',
    '__bases__', '__subclasses__', '__mro__', '__getattribute__',
    '__getattr__', '__setattr__', '__delattr__', '__new__', '__init__',
    '__reduce__', '__reduce_ex__', '__str__', '__repr__', '__bytes__',
    '__format__', '__dir__', '__getstate__', '__setstate__',
    '__getinitargs__', '__getnewargs__', '__module__', '__annotations__',
    '__doc__', '__name__', '__qualname__'
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
            elif module_name not in ALLOWED_MODULES:
                self.errors.append({
                    'type': '模块建议',
                    'line': node.lineno,
                    'column': node.col_offset,
                    'message': f'不建议使用模块: {name.name}',
                    'suggestion': '建议使用math、random、collections等游戏开发常用模块'
                })
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        """检查from...import语句"""
        if node.module:
            module_name = node.module.split('.')[0]
            if module_name in DANGEROUS_MODULES:
                self.errors.append({
                    'type': '安全警告',
                    'line': node.lineno,
                    'column': node.col_offset,
                    'message': f'禁止导入危险模块: {node.module}',
                    'suggestion': '此模块可能会访问系统资源，请移除'
                })
                self.has_errors = True
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        """检查属性访问"""
        if isinstance(node.attr, str) and node.attr in DANGEROUS_ATTRIBUTES:
            self.errors.append({
                'type': '安全警告',
                'line': node.lineno,
                'column': node.col_offset,
                'message': f'禁止访问危险属性: {node.attr}',
                'suggestion': '此属性可能绕过安全限制，请使用普通的属性访问方式'
            })
            self.has_errors = True
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
