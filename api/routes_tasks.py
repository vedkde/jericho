from fastapi import APIRouter, HTTPException
from tasks.registry import list_tasks, get_task

router = APIRouter()

@router.get("/")
def get_tasks():
    return {
        "tasks": list_tasks(),
        "action_schema": {
            "edit": {
                "type": "edit",
                "new_code": "<full corrected code as string>"
            },
            "run_tests": {
                "type": "run_tests"
            }
        }
    }

@router.get("/{task_id}")
def get_task_by_id(task_id: str):
    try:
        task = get_task(task_id)
        return {
            "task_id": task_id,
            "difficulty": task["difficulty"],
            "description": task["description"],
            "total_tests": task["total_tests"],
            "buggy_code": task["buggy_code"],
            "functions": task.get("functions", []),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))