from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from env import DebugEnv
from env.state import EnvState

router = APIRouter()

# in-memory session store
sessions: dict[str, DebugEnv] = {}

class ResetRequest(BaseModel):
    session_id: str
    task_id: str

class StepRequest(BaseModel):
    session_id: str
    action: dict

def state_to_dict(state: EnvState) -> dict:
    return {
        "code": state.code,
        "last_test_output": state.last_test_output,
        "tests_passed": state.tests_passed,
        "tests_total": state.tests_total,
        "step_count": state.step_count,
        "done": state.done
    }

@router.post("/reset")
def reset(req: ResetRequest):
    try:
        env = DebugEnv()
        state = env.reset(req.task_id)
        sessions[req.session_id] = env
        return {
            "session_id": req.session_id,
            "task_id": req.task_id,
            "state": state_to_dict(state)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/step")
def step(req: StepRequest):
    env = sessions.get(req.session_id)
    if not env:
        raise HTTPException(status_code=404, detail=f"Session '{req.session_id}' not found. Call /reset first.")
    try:
        state, reward, done = env.step(req.action)
        return {
            "session_id": req.session_id,
            "state": state_to_dict(state),
            "reward": reward,
            "done": done
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.get("/state/{session_id}")
def state(session_id: str):
    env = sessions.get(session_id)
    if not env:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return {
        "session_id": session_id,
        "state": state_to_dict(env.state())
    }