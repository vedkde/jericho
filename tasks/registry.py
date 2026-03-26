from tasks.easy_task import EASY_TASK
from tasks.medium_task import MEDIUM_TASK
from tasks.hard_task import HARD_TASK

TASK_REGISTRY = {
    "easy": EASY_TASK,
    "medium": MEDIUM_TASK,
    "hard": HARD_TASK,
}

def get_task(task_id: str) -> dict:
    if task_id not in TASK_REGISTRY:
        raise ValueError(
            f"Unknown task_id: '{task_id}'. "
            f"Available tasks: {list(TASK_REGISTRY.keys())}"
        )
    return TASK_REGISTRY[task_id]

def list_tasks() -> list:
    return [
        {
            "task_id": task_id,
            "description": task["description"],
            "difficulty": task["difficulty"],
            "total_tests": task["total_tests"],
        }
        for task_id, task in TASK_REGISTRY.items()
    ]