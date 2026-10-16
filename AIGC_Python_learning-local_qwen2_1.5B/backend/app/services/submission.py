"""Server-owned exercises and deterministic judging; legacy IDs stay stable."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.sandbox.runner import run_code_process
from app.services.problem_catalog import Problem, TestCase, PROBLEMS, GREETING, GREETING_ID


class ExecutionError(BaseModel):
    type: str
    line: int | None = None
    message: str


class CaseResult(BaseModel):
    case_id: str
    passed: bool
    expected_output: str
    actual_output: str
    output_available: bool = True
    errors: list[ExecutionError]
    execution_time: float
    visibility: Literal['public', 'hidden'] = 'public'


class JudgeResult(BaseModel):
    status: Literal["accepted", "wrong_answer", "execution_error", "timeout"]
    passed: bool
    passed_cases: int
    total_cases: int
    cases: list[CaseResult]


class SubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem_id: str
    code: str = Field(min_length=1, max_length=6000)

    @field_validator("code")
    @classmethod
    def nonblank_code(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("请输入代码")
        return value


def judge_submission(problem: Problem, code: str) -> JudgeResult:
    cases = []
    for test in problem.tests:
        execution = run_code_process(code, timeout=getattr(problem, 'time_limit_seconds', 3), stdin=test.stdin)
        actual = execution['output'].replace('\r\n', '\n')
        expected = test.expected_output.replace('\r\n', '\n')
        matches = actual == expected if problem.comparison == 'exact' else actual.strip() == expected.strip()
        cases.append(CaseResult(
            case_id=test.case_id,
            passed=execution["success"] and matches,
            expected_output=test.expected_output,
            actual_output=execution["output"],
            output_available=execution.get("output_available", True),
            errors=[ExecutionError(type=error["type"], line=error.get("line"), message=error["message"])
                    for error in execution["errors"]],
            execution_time=execution["execution_time"],
            visibility=test.visibility,
        ))
    passed_cases = sum(case.passed for case in cases)
    passed = passed_cases == len(cases)
    status = "accepted" if passed else "wrong_answer"
    if any(error.type == "超时警告" for case in cases if not case.passed for error in case.errors):
        status = "timeout"
    elif any(case.errors for case in cases if not case.passed):
        status = "execution_error"
    return JudgeResult(status=status, passed=passed, passed_cases=passed_cases, total_cases=len(cases), cases=cases)


def public_judge(judge: JudgeResult) -> JudgeResult:
    """Redact before persistence, teaching analysis, and every student response."""
    result = judge.model_copy(deep=True)
    for case in result.cases:
        if case.visibility == 'hidden':
            case.expected_output = ''
            case.actual_output = ''
            case.errors = []
            case.output_available = False
    return result
