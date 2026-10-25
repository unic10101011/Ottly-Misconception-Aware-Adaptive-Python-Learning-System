"""Preserve validated cloud feedback and explicit service errors."""
from app.services.error_analysis import AnalysisResult
from app.services.problem_catalog import Lesson
from app.services.submission import JudgeResult


def with_lesson_hints(lesson: Lesson, analysis: AnalysisResult, judge: JudgeResult) -> AnalysisResult:
    return analysis
