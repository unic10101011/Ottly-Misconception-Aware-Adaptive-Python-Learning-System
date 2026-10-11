from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.sandbox.sandbox import run_code

router = APIRouter()


class CodeRunRequest(BaseModel):
    code: str = Field(..., description="Python code to execute")
    timeout: int = Field(default=10, description="Execution timeout in seconds")


class CodeRunResponse(BaseModel):
    code: int = 200
    msg: str = "执行成功"
    data: dict = {}


@router.post("/code/run")
async def execute_code(request: CodeRunRequest):
    result = run_code(request.code, timeout=request.timeout)

    return CodeRunResponse(
        code=200,
        msg="执行成功" if result["success"] else "代码有错误",
        data={
            "success": result["success"],
            "output": result["output"],
            "errors": result["errors"],
            "execution_time": result["execution_time"],
        },
    )
