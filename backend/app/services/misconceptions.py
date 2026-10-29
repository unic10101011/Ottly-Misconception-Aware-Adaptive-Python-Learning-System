"""Shared, fixed vocabulary for analysis and practice metadata."""
from typing import Literal

MisconceptionTag = Literal[
    'range_boundary', 'accumulation_error', 'condition_error',
    'variable_error', 'syntax_error', 'other',
]
MISCONCEPTION_TAGS = {
    'range_boundary', 'accumulation_error', 'condition_error',
    'variable_error', 'syntax_error', 'other',
}

# Shared by generation and review; these are categories, not case-specific answers.
MISCONCEPTION_DEFINITIONS = {
    'range_boundary': 'range 循环的起点、终点或步长错误；不能仅因列表下标越界就归入此类。',
    'accumulation_error': '累计、计数或循环推进变量的初始化、保留或更新错误。',
    'condition_error': '比较、布尔表达式或分支条件错误。',
    'variable_error': '变量名字、作用域、生命周期或变量间取值使用错误；字符串中原样输出变量名不归入此类。',
    'syntax_error': '公开执行证据明确表明语法解析失败。',
    'other': '当前错因不属于上述类别，或没有足够证据支持具体类别；例如字符串字面量替代变量值、单独的列表下标越界。',
}
