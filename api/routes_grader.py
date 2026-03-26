from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from env.executor import Executor
from tasks.registry import get_task

router = APIRouter()
executor = Executor()

class GraderRequest(BaseModel):
    task_id: str
    code: str

@router.post("/")
def grade(req: GraderRequest):
    try:
        task = get_task(req.task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    result = executor.run(
        code=req.code,
        test_code=task["test_code"]
    )

    total = task["total_tests"]
    passed = result["passed"]
    score = round(passed / total, 4) if total > 0 else 0.0

    return {
        "task_id": req.task_id,
        "passed": passed,
        "total": total,
        "score": score,
        "output": result["output"],
        "timed_out": result["timed_out"]
    }