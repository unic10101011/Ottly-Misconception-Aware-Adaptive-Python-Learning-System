from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool
from app.core.auth import get_current_user
from pydantic import BaseModel, Field
from app.services.sandbox.runner import run_code_process
from app.services.submission import PROBLEMS, JudgeResult, SubmissionRequest, judge_submission
from app.services.error_analysis import AnalysisResult, analyze_failure

router = APIRouter(dependencies=[Depends(get_current_user)])


class CodeRunRequest(BaseModel):
    code: str = Field(..., max_length=20000, description="Python code to execute")
    timeout: int = Field(default=10, ge=1, le=10, description="Execution timeout in seconds")


class CodeRunResponse(BaseModel):
    code: int = 200
    msg: str = "执行成功"
    data: dict = {}


@router.post("/code/run")
def execute_code(request: CodeRunRequest):
    result = run_code_process(request.code, timeout=request.timeout)

    return CodeRunResponse(
        code=200,
        msg="执行成功" if result["success"] else "代码有错误",
        data={
            "success": result["success"],
            "output": result["output"],
            "output_available": result["output_available"],
            "errors": result["errors"],
            "execution_time": result["execution_time"],
        },
    )


class SubmissionData(BaseModel):
    problem_id: str
    judge: JudgeResult
    analysis: AnalysisResult


class SubmissionResponse(BaseModel):
    code: int = 200
    data: SubmissionData


@router.post("/code/submit", response_model=SubmissionResponse)
async def submit_code(request: SubmissionRequest):
    problem = PROBLEMS.get(request.problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    judge = await run_in_threadpool(judge_submission, problem, request.code)
    analysis = await analyze_failure(problem, request.code, judge)
    return SubmissionResponse(data=SubmissionData(problem_id=problem.problem_id, judge=judge, analysis=analysis))
