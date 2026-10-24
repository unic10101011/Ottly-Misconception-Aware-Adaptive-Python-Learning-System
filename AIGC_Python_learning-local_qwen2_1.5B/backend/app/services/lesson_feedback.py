"""Reviewed lesson guidance when the unchanged AI pipeline cannot provide hints."""
from app.services.error_analysis import AnalysisContent, AnalysisResult, Evidence, Hints, safe_hints
from app.services import error_analysis
from app.services.problem_catalog import KNOWLEDGE, LEVELS, Lesson
from app.services.submission import JudgeResult


def with_lesson_hints(lesson: Lesson, analysis: AnalysisResult, judge: JudgeResult) -> AnalysisResult:
    # Preserve cloud setup/service errors instead of disguising them as a ready diagnosis.
    if judge.passed or analysis.status == 'ready' or error_analysis.ANALYSIS_PROVIDER == 'deepseek':
        return analysis
    if not any(slot.problem_id == lesson.problem_id for slot in LEVELS):
        return analysis
    visible = next((case for case in judge.cases if case.visibility == 'public'
                    and (case.errors or case.output_available)), None)
    if visible is None or any(error.type == 'RunnerError' for case in judge.cases for error in case.errors):
        return analysis
    # Keep the model response untouched when valid. This fallback makes no diagnosis
    # and uses only already-redacted public judge evidence, including an empty output.
    error_types = {error.type for case in judge.cases for error in case.errors}
    hints = (safe_hints(lesson.execution_problem(), judge)
             if error_types & {'语法错误', 'SyntaxError', 'IndentationError', 'NameError'}
             else Hints.model_validate(lesson.hints.model_dump()))
    return AnalysisResult(
        status='ready', source='fixed',
        message='AI 暂未提供合格分析，以下使用本关已审核的基础提示。',
        model_load_ms=analysis.model_load_ms,
        content=AnalysisContent(
            suspected_cause='尚未确认具体错因，请结合公开结果逐步核对。',
            evidence=[Evidence(
                case_id=visible.case_id,
                field='error_message' if visible.errors else 'actual_output',
                quote=(visible.errors[0].message if visible.errors else visible.actual_output)[:1000],
                explanation='这里只引用公开样例的执行结果，不推测隐藏测试内容。',
            )],
            knowledge_points=[KNOWLEDGE[key].name for key in lesson.knowledge_ids],
            hints=hints,
        ),
    )
