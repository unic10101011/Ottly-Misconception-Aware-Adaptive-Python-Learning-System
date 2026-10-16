"""Deterministic public/record adapters, separate from the unchanged model pipeline."""
import ast
from datetime import timezone
from typing import Literal

from pydantic import Field, computed_field

from app.services.error_analysis import AnalysisContent, AnalysisResult
from app.services.problem_catalog import KNOWLEDGE_ALIASES, Lesson, alias_key
from app.services.submission import JudgeResult, public_judge

ERROR_CODES = {
    'SyntaxError': 'SYNTAX_ERROR', '语法错误': 'SYNTAX_ERROR',
    'IndentationError': 'INDENTATION_ERROR', 'TabError': 'INDENTATION_ERROR',
    'NameError': 'NAME_ERROR', 'UnboundLocalError': 'NAME_ERROR',
    'TypeError': 'TYPE_ERROR', 'ValueError': 'VALUE_ERROR',
    'ZeroDivisionError': 'ZERO_DIVISION_ERROR', 'IndexError': 'INDEX_ERROR',
    'KeyError': 'KEY_ERROR', 'AttributeError': 'ATTRIBUTE_ERROR',
    'EOFError': 'EOF_ERROR', 'ImportError': 'IMPORT_ERROR', 'ModuleNotFoundError': 'IMPORT_ERROR',
    '安全警告': 'SECURITY_ERROR', 'OutputLimitError': 'OUTPUT_LIMIT_EXCEEDED',
    '超时警告': 'TIMEOUT', 'wrong_answer': 'WRONG_ANSWER',
    'RequirementError': 'REQUIREMENT_NOT_MET',
}
STUDENT_ERRORS = set(ERROR_CODES.values()) | {'RUNTIME_ERROR'}


def error_code(raw: str | None, *, code: str | None = None) -> str:
    # The original sandbox groups indentation under SyntaxError. Recover the
    # precise category without changing any evidence passed to the model.
    if code is not None and raw in {'语法错误', 'SyntaxError', 'SYNTAX_ERROR'}:
        try:
            ast.parse(code)
        except IndentationError:
            return 'INDENTATION_ERROR'
        except SyntaxError:
            pass
    return raw if raw in STUDENT_ERRORS else ERROR_CODES.get(raw, 'RUNTIME_ERROR')


class ContractJudge(JudgeResult):
    @computed_field
    @property
    def failed_tests(self) -> list[str]:
        return [case.case_id for case in self.cases if not case.passed]


class ContractAnalysisContent(AnalysisContent):
    knowledge_ids: list[str] = Field(default_factory=list)


class ContractAnalysis(AnalysisResult):
    source: Literal['ai', 'fixed'] | None = None
    content: ContractAnalysisContent | None = None


def submission_error(judge: JudgeResult, raw: str | None = None, *, code: str | None = None) -> str | None:
    if judge.passed:
        return None
    if judge.status == 'timeout':
        return 'TIMEOUT'
    if judge.status == 'wrong_answer':
        return 'WRONG_ANSWER'
    first = next((error.type for case in judge.cases if not case.passed for error in case.errors), raw)
    return error_code(first, code=code)


def contract_judge(judge: JudgeResult | dict, *, code: str | None = None) -> ContractJudge:
    if isinstance(judge, dict):
        # Older stored results never had failed_tests. Always derive it afresh.
        judge = JudgeResult.model_validate(judge)
    result = public_judge(judge)
    for case in result.cases:
        for error in case.errors:
            error.type = error_code(error.type, code=code)
    return ContractJudge(**result.model_dump())


def contract_analysis(analysis: AnalysisResult | dict | None, allowed_ids: list[str]) -> ContractAnalysis | None:
    if analysis is None:
        return None
    data = analysis.model_dump(mode='json') if isinstance(analysis, AnalysisResult) else dict(analysis)
    if data.get('status') != 'ready':
        data['content'] = None
        data['source'] = None
        if data.get('status') == 'skipped':
            data['model'] = None
    elif data.get('content'):
        content = dict(data['content'])
        mapped = [KNOWLEDGE_ALIASES.get(alias_key(text)) for text in content.get('knowledge_points', [])]
        content['knowledge_ids'] = list(dict.fromkeys(key for key in mapped if key in allowed_ids))
        data['content'] = content
        if data.get('source') == 'fixed':
            data['model'] = None
    return ContractAnalysis.model_validate(data)


def analysis_knowledge_scope(problem: Lesson) -> list[str]:
    return list(dict.fromkeys([*problem.knowledge_ids, *problem.prerequisite_knowledge_ids]))


def utc_iso(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def snapshot_fields(record):
    return {
        'schema_version': record.schema_version,
        'version': record.problem_version,
        'difficulty': record.difficulty,
        'knowledge_ids': list(record.knowledge_ids or []),
    }


def history_analysis(record, judge: ContractJudge):
    data = record.analysis_json
    if not data:
        return None
    if data.get('status') == 'ready' and data.get('content'):
        public_ids = {case.case_id for case in judge.cases if case.visibility == 'public'}
        if any(item.get('case_id') not in public_ids for item in data['content'].get('evidence', [])):
            return ContractAnalysis(status='invalid_response', message='历史分析含不可公开的测试依据，已隐藏；判题结果仍保留。')
        # New records freeze mappings at submission time. Do not remap with today's aliases.
        if record.schema_version and 'knowledge_ids' in data['content']:
            return ContractAnalysis.model_validate(data)
    return contract_analysis(data, record.knowledge_ids or [])
