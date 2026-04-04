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

    # step 2 — apply the known solution function by function
    if not done:
        solution_code = task["solution_code"]
        functions     = task.get("functions", [])

        import re
        for fn_name in functions:
            if done:
                break

            # extract the function body from solution_code
            lines = solution_code.split("\n")
            start_idx = None
            for i, line in enumerate(lines):
                if re.match(rf"^def {re.escape(fn_name)}\s*\(", line):
                    start_idx = i
                    break

            if start_idx is None:
                continue

            end_idx = len(lines)
            for i in range(start_idx + 1, len(lines)):
                line = lines[i]
                if line and not line[0].isspace() and line.strip() != "":
                    end_idx = i
                    break

            fn_code = "\n".join(lines[start_idx:end_idx]).strip()

            state, reward, done = env.step({
                "type": "edit_function",
                "function_name": fn_name,
                "new_code": fn_code
            })
            total_reward += reward
            trajectory.append({
                "step": state.step_count,
                "action": f"edit_function ({fn_name})",
                "tests_passed": state.tests_passed,
                "reward": reward,
                "done": done
            })

    # step 3 — run tests after applying solution
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