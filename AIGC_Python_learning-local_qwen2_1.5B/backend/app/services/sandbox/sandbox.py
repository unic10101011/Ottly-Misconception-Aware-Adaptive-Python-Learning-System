"""
Python代码沙箱主执行程序
提供安全的代码执行环境
"""
import sys
import io
import threading
import time
from typing import Dict, Any, Optional, Callable
from contextlib import redirect_stdout, redirect_stderr

from .security_check import SecurityChecker
from .error_helper import ErrorHelper


class TimeoutException(Exception):
    """超时异常"""
    pass


class Sandbox:
    """Python代码沙箱"""
    
    def __init__(self, timeout: int = 10):
        """
        初始化沙箱
        
        Args:
            timeout: 执行超时时间（秒）
        """
        self.timeout = timeout
        self.security_checker = SecurityChecker()
        self.error_helper = ErrorHelper()
        
        # 受限制的全局命名空间
        self.safe_globals = self._create_safe_globals()
    
    def _create_safe_globals(self) -> Dict:
        """创建安全的全局命名空间"""
        safe_builtins = {}
        
        # 安全的内置函数白名单
        allowed_builtins = [
            'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes',
            'callable', 'chr', 'classmethod', 'complex', 'dict', 'dir', 'divmod',
            'enumerate', 'filter', 'float', 'format', 'frozenset', 'getattr',
            'hasattr', 'hash', 'help', 'hex', 'id', 'int', 'isinstance', 'issubclass',
            'iter', 'len', 'list', 'locals', 'map', 'max', 'min', 'next', 'object',
            'oct', 'ord', 'pow', 'print', 'property', 'range', 'repr', 'reversed',
            'round', 'set', 'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super',
            'tuple', 'type', 'zip', '__import__',
        ]
        
        # 构建安全的内置函数字典
        import builtins
        for name in allowed_builtins:
            if hasattr(builtins, name):
                safe_builtins[name] = getattr(builtins, name)
        
        # 重载危险函数
        safe_builtins['__import__'] = self._safe_import
        safe_builtins['open'] = self._safe_open
        
        return {
            '__builtins__': safe_builtins,
            '__name__': '__sandbox__',
            '__doc__': None,
        }
    
    def _safe_import(self, name, *args, **kwargs):
        """安全的import函数"""
        from .security_check import DANGEROUS_MODULES, ALLOWED_MODULES
        
        module_name = name.split('.')[0]
        
        if module_name in DANGEROUS_MODULES:
            raise ImportError(f'禁止导入模块: {name}')
        
        # 只允许导入白名单模块
        if module_name not in ALLOWED_MODULES:
            raise ImportError(f'不允许导入模块: {name}')
        
        # 真正的导入
        import importlib
        return importlib.__import__(name, *args, **kwargs)
    
    def _safe_open(self, *args, **kwargs):
        """安全的open函数（禁止使用）"""
        raise PermissionError('禁止文件读写操作')
    
    def execute(self, code: str) -> Dict[str, Any]:
        """
        在沙箱中执行代码
        
        Args:
            code: 要执行的Python代码
            
        Returns:
            执行结果字典
        """
        result = {
            'success': False,
            'output': '',
            'errors': [],
            'execution_time': 0,
        }
        
        # 1. 安全检查
        is_safe, security_errors = self.security_checker.check_code(code)
        result['errors'].extend(security_errors)
        
        if not is_safe:
            result['output'] = '⚠️ 发现安全问题，请检查代码后重试\n'
            return result
        
        # 2. 执行代码
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        start_time = time.time()
        
        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                self._execute_with_timeout(code)
            
            result['success'] = True
            result['output'] = stdout_capture.getvalue()
            
        except TimeoutException:
            result['errors'].append({
                'type': '超时警告',
                'line': None,
                'column': None,
                'message': f'代码执行超过 {self.timeout} 秒，已自动终止',
                'suggestion': '检查是否有死循环或无限递归，或者优化代码逻辑'
            })
            result['output'] = stdout_capture.getvalue()
            
        except Exception as e:
            # 处理运行时错误
            exc_type, exc_value, exc_traceback = sys.exc_info()
            error_info = self.error_helper.format_error(
                exc_type, exc_value, exc_traceback
            )
            
            result['errors'].append({
                'type': error_info['type'],
                'line': error_info['line'],
                'column': error_info['column'],
                'message': error_info['friendly_message'],
                'suggestion': '\n'.join(error_info['suggestions'])
            })
            
            result['output'] = stdout_capture.getvalue()
            if stderr_capture.getvalue():
                result['output'] += '\n' + stderr_capture.getvalue()
        
        finally:
            result['execution_time'] = round(time.time() - start_time, 3)
        
        return result
    
    def _execute_with_timeout(self, code: str):
        """带超时检测的代码执行"""
        result = {'exception': None}
        
        def target():
            try:
                exec(code, self.safe_globals, {})
            except Exception as e:
                result['exception'] = e
        
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(self.timeout)
        
        if thread.is_alive():
            raise TimeoutException(f'执行超过 {self.timeout} 秒')
        
        if result['exception']:
            raise result['exception']


# 便捷函数
def run_code(code: str, timeout: int = 10) -> Dict[str, Any]:
    """
    便捷运行代码的函数
    
    Args:
        code: Python代码
        timeout: 超时时间
        
    Returns:
        执行结果
    """
    sandbox = Sandbox(timeout=timeout)
    return sandbox.execute(code)


if __name__ == '__main__':
    # 简单测试
    test_code = '''print('Hello, 沙箱测试!')'''
    result = run_code(test_code)
    print(result)
