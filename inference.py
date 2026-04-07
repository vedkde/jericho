from __future__ import annotations

import os
import sys
import uuid
import json
import re
import requests
from typing import Optional, List
from openai import OpenAI

# ── config ────────────────────────────────────────────────────────────────────

API_BASE_URL  = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME    = os.getenv("MODEL_NAME",   "meta-llama/Llama-3.3-70B-Instruct")
HF_TOKEN      = os.getenv("HF_TOKEN")
ENV_BASE_URL  = os.getenv("ENV_BASE_URL", "https://akkiisfrommars-jericho.hf.space")
BENCHMARK     = "jericho"
MAX_STEPS     = 20
TASKS         = ["easy", "medium", "hard"]

if not HF_TOKEN:
    print("ERROR: HF_TOKEN environment variable is not set.")
    sys.exit(1)

client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)

# ── logging (required stdout format) ─────────────────────────────────────────

def log_start(task: str, env: str, model: str):
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]):
    error_val = error if error else "null"
    print(f"[STEP] step={step} action={action} reward={reward:.2f} done={str(done).lower()} error={error_val}", flush=True)

def log_end(success: bool, steps: int, score: float, rewards: List[float]):
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}", flush=True)

# ── environment helpers ───────────────────────────────────────────────────────

def env_reset(session_id: str, task_id: str) -> dict:
    resp = requests.post(f"{ENV_BASE_URL}/env/reset", json={
        "session_id": session_id,
        "task_id": task_id
    })
    resp.raise_for_status()
    return resp.json()["state"]

def env_step(session_id: str, action: dict):
    resp = requests.post(f"{ENV_BASE_URL}/env/step", json={
        "session_id": session_id,
        "action": action
    })
    resp.raise_for_status()
    data = resp.json()
    reward = data["reward"]
    if isinstance(reward, dict):
        reward = reward["value"]
    return data["state"], float(reward), data["done"]

def env_grade(task_id: str, code: str) -> dict:
    resp = requests.post(f"{ENV_BASE_URL}/grader/", json={
        "task_id": task_id,
        "code": code
    })
    resp.raise_for_status()
    return resp.json()

def get_task_info(task_id: str) -> dict:
    resp = requests.get(f"{ENV_BASE_URL}/tasks/{task_id}")
    resp.raise_for_status()
    return resp.json()

# ── LLM helpers ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert Python debugger. You will be given buggy Python code and test failure output.

Your job is to fix ONE function at a time. When you decide which function to fix, respond in this exact JSON format:

{
  "function_name": "the_function_to_fix",
  "fixed_code": "def the_function_to_fix(...):\\n    # complete corrected function body here"
}

Rules:
- Output ONLY valid JSON. No explanation, no markdown, no code fences.
- The fixed_code must be a complete function definition starting with def.
- Fix only ONE function per response.
- Choose the function most likely causing current test failures.
- If all tests pass, output: {"done": true}
"""

def ask_llm(code: str, test_output: str, functions: List[str], tests_passed: int, tests_total: int) -> Optional[dict]:
    user_message = f"""Current code:
{code}

Test results: {tests_passed}/{tests_total} passing

Test output:
{test_output[-3000:] if len(test_output) > 3000 else test_output}

Available functions to fix: {functions}

Which single function should be fixed, and what is the corrected version?"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message}
            ],
            max_tokens=1024,
            temperature=0.2,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
    except Exception as e:
        return None

# ── agent loop ────────────────────────────────────────────────────────────────

def run_task(task_id: str) -> dict:
    session_id   = f"{task_id}-{uuid.uuid4().hex[:8]}"
    task_info    = get_task_info(task_id)
    functions    = task_info.get("functions", [])
    rewards      = []
    steps_taken  = 0
    score        = 0.0
    success      = False
    error        = None

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
        state = env_reset(session_id, task_id)

        # initial test run
        state, reward, done = env_step(session_id, {"type": "run_tests"})
        rewards.append(reward)
        steps_taken += 1
        log_step(step=steps_taken, action="run_tests", reward=reward, done=done, error=None)

        while not done and steps_taken < MAX_STEPS:
            if state["tests_passed"] == state["tests_total"]:
                break

            llm_response = ask_llm(
                code         = state["code"],
                test_output  = state["last_test_output"],
                functions    = functions,
                tests_passed = state["tests_passed"],
                tests_total  = state["tests_total"],
            )

            if llm_response is None or llm_response.get("done"):
                state, reward, done = env_step(session_id, {"type": "run_tests"})
                rewards.append(reward)
                steps_taken += 1
                log_step(step=steps_taken, action="run_tests", reward=reward, done=done, error="llm_parse_error")
                continue

            fn_name = llm_response.get("function_name")
            fn_code = llm_response.get("fixed_code")

            if not fn_name or not fn_code:
                state, reward, done = env_step(session_id, {"type": "run_tests"})
                rewards.append(reward)
                steps_taken += 1
                log_step(step=steps_taken, action="run_tests", reward=reward, done=done, error="missing_fields")
                continue

            # edit
            action_str = f"edit_function({fn_name})"
            state, reward, done = env_step(session_id, {
                "type":          "edit_function",
                "function_name": fn_name,
                "new_code":      fn_code,
            })
            rewards.append(reward)
            steps_taken += 1
            log_step(step=steps_taken, action=action_str, reward=reward, done=done, error=None)

            # run tests after edit
            if not done:
                state, reward, done = env_step(session_id, {"type": "run_tests"})
                rewards.append(reward)
                steps_taken += 1
                log_step(step=steps_taken, action="run_tests", reward=reward, done=done, error=None)

        grade   = env_grade(task_id, state["code"])
        score   = grade["score"]
        success = score == 1.0

    except Exception as e:
        error = str(e)

    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return {
        "task_id": task_id,
        "score":   score,
        "steps":   steps_taken,
        "success": success,
        "rewards": rewards,
    }

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    results = []
    for task_id in TASKS:
        try:
            result = run_task(task_id)
            results.append(result)
        except Exception as e:
            results.append({"task_id": task_id, "score": 0.0, "error": str(e)})

    avg = sum(r.get("score", 0) for r in results) / len(results)
    with open("baseline_results.json", "w") as f:
        json.dump({"model": MODEL_NAME, "tasks": results, "average": round(avg, 4)}, f, indent=2)

if __name__ == "__main__":
    main()
