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
