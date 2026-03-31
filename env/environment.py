import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.state import EnvState
from env.executor import Executor
from env.reward import compute_reward
from env.models import Observation, Action, Reward
from tasks.registry import get_task
import re

MAX_STEPS = 20


class DebugEnv:
    def __init__(self):
        self.task = None
        self.current_state = None
        self.executor = Executor()

    def reset(self, task_id: str) -> Observation:
        self.task = get_task(task_id)
        self.current_state = EnvState(
            code=self.task["buggy_code"],
            test_code=self.task["test_code"],
            last_test_output="",
            tests_passed=0,
            tests_total=self.task["total_tests"],
            step_count=0,
            done=False
        )
        return self._to_observation(self.current_state)

    def step(self, action: Action) -> tuple[Observation, Reward, bool]:
        if self.current_state is None:
            raise RuntimeError("Call reset() before step()")
        if self.current_state.done:
            raise RuntimeError("Episode is done. Call reset() to start a new one.")

        # accept both Pydantic Action and raw dict for backwards compatibility
        if isinstance(action, dict):
            action = Action(**action)

        old_state = self.current_state.copy()

        if action.type == "edit_function":
            self._apply_function_edit(action)
        elif action.type == "run_tests":
            self._run_tests()
        else:
            raise ValueError(
                f"Unknown action type: '{action.type}'. "
                f"Must be 'edit_function' or 'run_tests'."
            )

        self.current_state.step_count += 1

        if self.current_state.tests_passed == self.current_state.tests_total:
            self.current_state.done = True
        elif self.current_state.step_count >= MAX_STEPS:
            self.current_state.done = True

        reward_value = compute_reward(old_state, self.current_state)
        reward = Reward(value=reward_value)

        return self._to_observation(self.current_state), reward, self.current_state.done

    def state(self) -> Observation:
        if self.current_state is None:
            raise RuntimeError("Call reset() first.")
        return self._to_observation(self.current_state)

    # ── internal helpers ───────────────────────────────────────────

    def _to_observation(self, state: EnvState) -> Observation:
        return Observation(
            code=state.code,
            tests_passed=state.tests_passed,
            tests_total=state.tests_total,
            last_test_output=state.last_test_output,
            step_count=state.step_count,
            done=state.done
        )

    def _apply_function_edit(self, action: Action):
        if not action.function_name:
            raise ValueError("edit_function action requires 'function_name' field.")
        if not action.new_code:
            raise ValueError("edit_function action requires 'new_code' field.")

        updated_code = self._replace_function(
            self.current_state.code,
            action.function_name,
            action.new_code
        )
        self.current_state.code = updated_code

    def _replace_function(self, source: str, function_name: str, new_function_code: str) -> str:
        lines = source.split("\n")
        start_idx = None
        end_idx = None

        for i, line in enumerate(lines):
            if re.match(rf"^def {re.escape(function_name)}\s*\(", line):
                start_idx = i
                break

        if start_idx is None:
            raise ValueError(
                f"Function '{function_name}' not found in current code. "
                f"Available functions: {self._get_function_names()}"
            )

        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if line and not line[0].isspace() and line.strip() != "":
                end_idx = i
                break

        if end_idx is None:
            end_idx = len(lines)

        before   = lines[:start_idx]
        after    = lines[end_idx:]
        new_lines = new_function_code.strip().split("\n")
        updated  = before + new_lines + [""] + after

        return "\n".join(updated)

    def _get_function_names(self) -> list:
        names = []
        for line in self.current_state.code.split("\n"):
            match = re.match(r"^def (\w+)\s*\(", line)
            if match:
                names.append(match.group(1))
        return names

    def _run_tests(self):
        result = self.executor.run(
            code=self.current_state.code,
            test_code=self.current_state.test_code
        )
        self.current_state.last_test_output = result["output"]
        self.current_state.tests_passed     = result["passed"]