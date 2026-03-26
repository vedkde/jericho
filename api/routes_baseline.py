from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from env import DebugEnv
from tasks.registry import get_task

router = APIRouter()

class BaselineRequest(BaseModel):
    task_id: str

@router.post("/")
def run_baseline(req: BaselineRequest):
    try:
        task = get_task(req.task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    env = DebugEnv()
    state = env.reset(req.task_id)

    trajectory = []
    total_reward = 0.0

    # step 1 — run tests to see initial state
    state, reward, done = env.step({"type": "run_tests"})
    total_reward += reward
    trajectory.append({
        "step": state.step_count,
        "action": "run_tests",
        "tests_passed": state.tests_passed,
        "reward": reward,
        "done": done
    })

    # step 2 — apply the known solution and run tests
    if not done:
        state, reward, done = env.step({
            "type": "edit",
            "new_code": task["solution_code"]
        })
        total_reward += reward
        trajectory.append({
            "step": state.step_count,
            "action": "edit (apply solution)",
            "tests_passed": state.tests_passed,
            "reward": reward,
            "done": done
        })

    if not done:
        state, reward, done = env.step({"type": "run_tests"})
        total_reward += reward
        trajectory.append({
            "step": state.step_count,
            "action": "run_tests",
            "tests_passed": state.tests_passed,
            "reward": reward,
            "done": done
        })

    final_score = round(state.tests_passed / state.tests_total, 4) if state.tests_total > 0 else 0.0

    return {
        "task_id": req.task_id,
        "total_steps": state.step_count,
        "total_reward": round(total_reward, 4),
        "final_score": final_score,
        "tests_passed": state.tests_passed,
        "tests_total": state.tests_total,
        "done": done,
        "trajectory": trajectory
    }