from pydantic import BaseModel
from typing import Optional


class Observation(BaseModel):
    code: str
    tests_passed: int
    tests_total: int
    last_test_output: str
    step_count: int
    done: bool


class Action(BaseModel):
    type: str                          # "run_tests" or "edit_function"
    function_name: Optional[str] = None
    new_code: Optional[str] = None


class Reward(BaseModel):
    value: float