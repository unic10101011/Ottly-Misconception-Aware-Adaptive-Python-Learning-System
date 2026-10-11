"""
错误提示与建议模块
提供友好易懂的错误信息和修改建议
"""
import traceback
import re
from typing import List, Dict, Tuple


class ErrorHelper:
    """错误处理助手"""
    
    # 常见错误类型提示模板
    ERROR_PATTERNS = {
        'SyntaxError': {
            'messages': {
                'invalid syntax': '语法格式不对，检查括号、冒号、引号是否正确',
                'EOL while scanning string literal': '字符串没写完，检查引号是否配对',
                'unexpected indent': '缩进错误，Python使用4个空格或1个Tab缩进',
                'expected an indented block': '缺少缩进，if/for/while后面需要缩进',
                'name not defined': '变量未定义，检查变量名拼写是否正确',
            },
            'suggestions': {
                'parentheses': '检查 () 圆括号是否正确配对',
                'quotes': '检查 "" 或 '' 引号是否正确配对',
                'colon': '检查 if/for/while/def 等语句后是否有冒号 :',
                'indent': '确保使用一致的缩进（建议4个空格）',
            }
        },
        'NameError': {
            'patterns': {
                r"name '(\w+)' is not defined": "变量 '{0}' 没有定义，请先赋值或检查拼写"
            },
            'suggestions': [
                '检查变量名是否拼写错误',
                '确保变量在使用前已赋值',
                '检查变量名的大小写是否正确（Python区分大小写）',
            ]
        },
        'TypeError': {
            'patterns': {
                r"can only concatenate str \(not \"(\w+)\"\) to str": "不能将 {0} 和字符串直接相加",
                r"unsupported operand type\(s\) for \+/: '(\w+)' and '(\w+)'": "{0} 和 {1} 类型不能一起运算",
                r"'(\w+)' object is not callable": "{0} 不是函数，不能加 () 调用",
                r"'(\w+)' object does not support item assignment": "{0} 类型不能修改其中的元素",
            },
            'suggestions': [
                '使用 str() 将数字转换为字符串',
                '使用 int() 或 float() 将字符串转换为数字',
                '检查是否把函数名当变量用了',
            ]
        },
        'IndexError': {
            'patterns': {
                r"list index out of range": "列表索引超出范围，检查列表长度",
                r"string index out of range": "字符串索引超出范围",
            },
            'suggestions': [
                '记住索引从 0 开始，最大索引是 len(list)-1',
                '使用 for item in list 遍历列表更安全',
            ]
        },
        'AttributeError': {
            'patterns': {
                r"'(\w+)' object has no attribute '(\w+)'": "{0} 对象没有 '{1}' 属性或方法",
            },
            'suggestions': [
                '检查方法名拼写是否正确',
                '确保使用正确的数据类型',
            ]
        },
        'ValueError': {
            'patterns': {
                r"invalid literal for int\(\) with base 10: '([^']+)'": "不能把 '{0}' 转换成数字",
                r"could not convert string to float: '([^']+)'": "不能把 '{0}' 转换成小数",
            },
            'suggestions': [
                '检查输入的数据格式是否正确',
                '使用 try-except 捕获可能的输入错误',
            ]
        },
        'ZeroDivisionError': {
            'suggestions': [
                '除数不能为 0，请检查计算逻辑',
                '在除法前添加判断条件 if y != 0',
            ]
        },
        'IndentationError': {
            'suggestions': [
                '确保所有代码块使用一致的缩进',
                '建议使用 4 个空格作为缩进',
                '不要混用空格和 Tab',
            ]
        },
        'KeyError': {
            'patterns': {
                r"'([^']+)'": "字典中没有 '{0}' 这个键",
            },
            'suggestions': [
                '使用 get() 方法更安全：dict.get(key, default)',
                '先检查键是否存在：if key in dict',
            ]
        },
    }
    
    @classmethod
    def format_error(cls, exc_type, exc_value, exc_traceback) -> Dict:
        """格式化错误信息"""
        error_info = {
            'type': exc_type.__name__,
            'message': str(exc_value),
            'line': None,
            'column': None,
            'suggestions': [],
            'friendly_message': ''
        }
        
        # 获取错误位置
        if exc_traceback:
            tb_frame = traceback.extract_tb(exc_traceback)[-1]
            error_info['line'] = tb_frame.lineno
            error_info['column'] = 0  # 简化处理
        
        # 生成友好提示
        error_info['friendly_message'], error_info['suggestions'] = cls._get_friendly_help(
            error_info['type'],
            error_info['message']
        )
        
        return error_info
    
    @classmethod
    def _get_friendly_help(cls, error_type: str, error_msg: str) -> Tuple[str, List[str]]:
        """获取友好的错误帮助信息"""
        suggestions = []
        friendly_msg = error_msg
        
        if error_type in cls.ERROR_PATTERNS:
            error_config = cls.ERROR_PATTERNS[error_type]
            
            # 尝试匹配具体错误模式
            if 'patterns' in error_config:
                for pattern, template in error_config['patterns'].items():
                    match = re.search(pattern, error_msg)
                    if match:
                        friendly_msg = template.format(*match.groups())
                        break
            
            # 添加通用建议
            if 'suggestions' in error_config:
                suggestions.extend(error_config['suggestions'])
            
            # 特殊处理
            if error_type == 'SyntaxError':
                if '(' in error_msg or ')' in error_msg:
                    suggestions.append('检查圆括号 () 是否正确配对')
                if '[' in error_msg or ']' in error_msg:
                    suggestions.append('检查方括号 [] 是否正确配对')
                if '{' in error_msg or '}' in error_msg:
                    suggestions.append('检查花括号 {} 是否正确配对')
                if ':' in error_msg:
                    suggestions.append('检查冒号 : 是否放在正确位置')
        
        # 为新手添加额外提示
        if not suggestions:
            suggestions = [
                '仔细检查这一行的语法',
                '可以参考教材中的例子对比',
                '试着把复杂代码拆分成简单步骤',
            ]
        
        return friendly_msg, suggestions
    
    @classmethod
    def format_for_display(cls, error_info: Dict) -> str:
        """格式化显示给用户的错误信息"""
        lines = []
        
        lines.append(f"⚠️ {error_info['type']}")
        if error_info['line']:
            lines.append(f"📍 第 {error_info['line']} 行")
        lines.append(f"❌ {error_info['friendly_message']}")
        lines.append("")
        lines.append("💡 建议修改：")
        for i, suggestion in enumerate(error_info['suggestions'], 1):
            lines.append(f"  {i}. {suggestion}")
        
        return '\n'.join(lines)
