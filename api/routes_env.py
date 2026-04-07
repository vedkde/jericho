from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from env import DebugEnv
from env.state import EnvState
import uuid

router = APIRouter()

sessions: dict = {}
_default_session_id = "default"

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
async def reset(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    task_id = body.get("task_id", "easy")
    session_id = body.get("session_id") or str(uuid.uuid4())

    try:
        env = DebugEnv()
        state = env.reset(task_id)
        sessions[session_id] = env
        sessions[_default_session_id] = env
        return {
            "session_id": session_id,
            "task_id": task_id,
            "state": state_to_dict(state)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/step")
async def step(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    session_id = body.get("session_id", _default_session_id)
    action = body.get("action", {"type": "run_tests"})

    env = sessions.get(session_id)
    if not env:
        env = sessions.get(_default_session_id)
    if not env:
        raise HTTPException(status_code=404, detail="No active session. Call /reset first.")

    try:
        state, reward, done, info = env.step(action)
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
