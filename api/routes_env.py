from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from env import DebugEnv
from env.state import EnvState
import uuid

router = APIRouter()

# in-memory session store
sessions: dict = {}

class ResetRequest(BaseModel):
    task_id: str
    session_id: Optional[str] = None

class StepRequest(BaseModel):
    action: dict
    session_id: Optional[str] = None

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
        session_id = req.session_id or str(uuid.uuid4())
        env = DebugEnv()
        state = env.reset(req.task_id)
        sessions[session_id] = env
        return {
            "session_id": session_id,
            "task_id": req.task_id,
            "state": state_to_dict(state)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/step")
def step(req: StepRequest):
    # if no session_id, use most recent session
    session_id = req.session_id
    if not session_id:
        if not sessions:
            raise HTTPException(status_code=404, detail="No active session. Call /reset first.")
        session_id = list(sessions.keys())[-1]

    env = sessions.get(session_id)
    if not env:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found. Call /reset first.")
    try:
        state, reward, done, info = env.step(req.action)
        return {
            "session_id": session_id,
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
