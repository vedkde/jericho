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

API_BASE_URL  = os.environ.get("API_BASE_URL",  "https://router.huggingface.co/v1")
MODEL_NAME    = os.environ.get("MODEL_NAME",    "meta-llama/Llama-3.3-70B-Instruct")
HF_TOKEN      = os.environ.get("HF_TOKEN",      "")
ENV_BASE_URL  = os.environ.get("ENV_BASE_URL",  "http://localhost:8000")

MAX_STEPS     = 20
TASKS         = ["easy", "medium", "hard"]

if not HF_TOKEN:
    print("ERROR: HF_TOKEN environment variable is not set.")
    sys.exit(1)

client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN,
)

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

    except json.JSONDecodeError as e:
        print(f"    [LLM] JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"    [LLM] API error: {e}")
        return None

# ── agent loop ────────────────────────────────────────────────────────────────

def run_task(task_id: str) -> dict:
    print(f"\n{'='*55}")
    print(f"  Task: {task_id.upper()}")
    print(f"{'='*55}")

    session_id = f"{task_id}-{uuid.uuid4().hex[:8]}"
    task_info  = get_task_info(task_id)
    functions  = task_info.get("functions", [])

    print(f"  Description : {task_info['description']}")
    print(f"  Total tests : {task_info['total_tests']}")
    print(f"  Functions   : {functions}")

    state = env_reset(session_id, task_id)
    print(f"\n  [reset] tests={state['tests_passed']}/{state['tests_total']} step=0")

    state, reward, done = env_step(session_id, {"type": "run_tests"})
    print(f"  [step 1] run_tests -> {state['tests_passed']}/{state['tests_total']} passing  reward={reward:.2f}")

    total_reward = reward
    trajectory   = []

    while not done and state["step_count"] < MAX_STEPS:
        if state["tests_passed"] == state["tests_total"]:
            break

        print(f"\n  [step {state['step_count']}] asking LLM...")

        llm_response = ask_llm(
            code         = state["code"],
            test_output  = state["last_test_output"],
            functions    = functions,
            tests_passed = state["tests_passed"],
            tests_total  = state["tests_total"],
        )

        if llm_response is None:
            print("    LLM returned invalid response, skipping.")
            state, reward, done = env_step(session_id, {"type": "run_tests"})
            total_reward += reward
            continue

        if llm_response.get("done"):
            print("    LLM says it is done.")
            break

        fn_name = llm_response.get("function_name")
        fn_code = llm_response.get("fixed_code")

        if not fn_name or not fn_code:
            print("    LLM response missing fields, skipping.")
            state, reward, done = env_step(session_id, {"type": "run_tests"})
            total_reward += reward
            continue

        print(f"    LLM chose to fix: {fn_name}")

        state, reward, done = env_step(session_id, {
            "type":          "edit_function",
            "function_name": fn_name,
            "new_code":      fn_code,
        })
        total_reward += reward
        print(f"    [edit] reward={reward:.2f}  tests={state['tests_passed']}/{state['tests_total']}")

        trajectory.append({
            "step":         state["step_count"],
            "function":     fn_name,
            "tests_passed": state["tests_passed"],
            "reward":       reward,
        })

        if not done:
            state, reward, done = env_step(session_id, {"type": "run_tests"})
            total_reward += reward
            print(f"    [tests] reward={reward:.2f}  tests={state['tests_passed']}/{state['tests_total']}  done={done}")

    grade = env_grade(task_id, state["code"])
    score = grade["score"]

    print(f"\n  -- Final result --")
    print(f"  Score        : {score:.4f}  ({grade['passed']}/{grade['total']} tests)")
    print(f"  Total reward : {total_reward:.4f}")
    print(f"  Steps taken  : {state['step_count']}")
    print(f"  Done         : {done}")

    return {
        "task_id":      task_id,
        "score":        score,
        "passed":       grade["passed"],
        "total":        grade["total"],
        "total_reward": round(total_reward, 4),
        "steps":        state["step_count"],
        "done":         done,
        "trajectory":   trajectory,
    }

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("\nJericho -- Baseline Inference")
    print(f"Model      : {MODEL_NAME}")
    print(f"API base   : {API_BASE_URL}")
    print(f"Env base   : {ENV_BASE_URL}")
    print(f"Tasks      : {TASKS}")

    results = []
    for task_id in TASKS:
        try:
            result = run_task(task_id)
            results.append(result)
        except Exception as e:
            print(f"\nERROR on task '{task_id}': {e}")
            results.append({"task_id": task_id, "score": 0.0, "error": str(e)})

    print(f"\n{'='*55}")
    print("  SUMMARY")
    print(f"{'='*55}")
    print(f"  {'Task':<10} {'Score':>8}  {'Passed':>8}  {'Steps':>6}")
    print(f"  {'-'*44}")
    for r in results:
        if "error" in r:
            print(f"  {r['task_id']:<10} {'ERROR':>8}  {r.get('error','')[:20]}")
        else:
            passed_str = f"{r['passed']}/{r['total']}"
            print(f"  {r['task_id']:<10} {r['score']:>8.4f}  {passed_str:>8}  {r['steps']:>6}")

    avg_score = sum(r.get("score", 0) for r in results) / len(results)
    print(f"\n  Average score: {avg_score:.4f}")
    print(f"{'='*55}\n")

    out_path = "baseline_results.json"
    with open(out_path, "w") as f:
        json.dump({"model": MODEL_NAME, "tasks": results, "average": round(avg_score, 4)}, f, indent=2)
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()