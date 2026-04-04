"""
Inference Script — Code Debugging Agent
===================================
MANDATORY
- Before submitting, ensure the following variables are defined in your environment configuration:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.

- The inference script must be named `inference.py` and placed in the root directory of the project
- Participants must use OpenAI Client for all LLM calls using above variables

STDOUT FORMAT
    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<0.00> rewards=<r1,r2,...,rn>
"""

import os
import sys
import json
import time
import requests

from openai import OpenAI

# ── env vars ───────────────────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY      = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
MODEL_NAME   = os.getenv("MODEL_NAME")

BASE_URL     = os.getenv("ENV_BASE_URL", "http://localhost:8000")
BENCHMARK    = "jericho-debug-env"


# ── logging helpers ────────────────────────────────────────────────
def log_start(task: str, model: str):
    print(f"[START] task={task} env={BENCHMARK} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: str = None):
    error_str = error if error else "null"
    done_str  = "true" if done else "false"
    print(f"[STEP] step={step} action={action} reward={reward:.2f} done={done_str} error={error_str}", flush=True)

def log_end(success: bool, steps: int, score: float, rewards: list):
    success_str  = "true" if success else "false"
    rewards_str  = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={success_str} steps={steps} score={score:.2f} rewards={rewards_str}", flush=True)


# ── LLM call via OpenAI client ─────────────────────────────────────
def ask_model(client: OpenAI, code: str, test_output: str, functions: list, attempt: int, extra_hint: str = "") -> dict:
    prompt = f"""You are a Python debugging assistant.

You are given buggy Python code and failing test output.
You must fix ONE function at a time per response.

AVAILABLE FUNCTIONS: {functions}

CURRENT CODE:
{code}

TEST OUTPUT:
{test_output}
{extra_hint}

Instructions:
- Carefully read ALL the test failures before deciding which function to fix
- Pick the ONE function most likely causing the remaining failures
- Return ONLY a JSON object with exactly two keys:
  - "function_name": the name of the function you are fixing
  - "new_code": the complete fixed function code as a string, no markdown, no fences
- Do not explain anything
- Do not fix multiple functions at once
- Return raw JSON only

Example:
{{"function_name": "compute_total", "new_code": "def compute_total(x, y):\\n    return x + y"}}
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a Python debugging assistant. Return only raw JSON."},
            {"role": "user",   "content": prompt}
        ],
        temperature=0.1,
        max_tokens=1024,
        stream=False,
    )

    raw = response.choices[0].message.content.strip()

    # strip markdown fences if model added them
    if "```" in raw:
        raw = "\n".join(l for l in raw.split("\n") if not l.strip().startswith("```")).strip()

    return json.loads(raw)


# ── single episode ─────────────────────────────────────────────────
def run_episode(client: OpenAI, task_id: str, session_id: str) -> tuple:
    log_start(task=task_id, model=MODEL_NAME)

    # fetch task metadata
    task_res = requests.get(f"{BASE_URL}/tasks/{task_id}")
    task_res.raise_for_status()
    task_data = task_res.json()
    functions = task_data.get("functions", [])

    # reset environment
    res = requests.post(f"{BASE_URL}/env/reset", json={"session_id": session_id, "task_id": task_id})
    res.raise_for_status()
    state = res.json()["state"]

    all_rewards     = []
    total_reward    = 0.0
    step_count      = 0
    attempt         = 1
    tried_functions = {}
    last_error      = None

    # initial test run
    res = requests.post(f"{BASE_URL}/env/step", json={"session_id": session_id, "action": {"type": "run_tests"}})
    res.raise_for_status()
    data   = res.json()
    state  = data["state"]
    reward = data["reward"]["value"] if isinstance(data["reward"], dict) else data["reward"]
    step_count += 1
    total_reward += reward
    all_rewards.append(reward)
    log_step(step=step_count, action="run_tests", reward=reward, done=state["done"])

    # agent loop
    while not state["done"]:
        stuck_hint = ""
        stuck = [f for f, c in tried_functions.items() if c >= 2]
        if stuck:
            stuck_hint = (
                f"\nWARNING: You already tried fixing {stuck} multiple times with no progress. "
                f"You MUST target a completely different function."
            )

        try:
            fix = ask_model(
                client=client,
                code=state["code"],
                test_output=state["last_test_output"],
                functions=functions,
                attempt=attempt,
                extra_hint=stuck_hint,
            )
            last_error = None
        except Exception as exc:
            last_error = str(exc)
            log_step(step=step_count + 1, action="ask_model", reward=0.00, done=False, error=last_error)
            break

        fn       = fix["function_name"]
        new_code = fix["new_code"]
        tried_functions[fn] = tried_functions.get(fn, 0) + 1

        action_str = f"edit_function({fn})"

        # apply fix
        res = requests.post(f"{BASE_URL}/env/step", json={
            "session_id": session_id,
            "action": {"type": "edit_function", "function_name": fn, "new_code": new_code}
        })
        if res.status_code == 400:
            log_step(step=step_count + 1, action=action_str, reward=0.00, done=True, error="step_limit_reached")
            break
        res.raise_for_status()
        data   = res.json()
        state  = data["state"]
        reward = data["reward"]["value"] if isinstance(data["reward"], dict) else data["reward"]
        step_count += 1
        total_reward += reward
        all_rewards.append(reward)
        log_step(step=step_count, action=action_str, reward=reward, done=state["done"])

        if state["done"]:
            break

        # run tests after fix
        res = requests.post(f"{BASE_URL}/env/step", json={
            "session_id": session_id,
            "action": {"type": "run_tests"}
        })
        if res.status_code == 400:
            log_step(step=step_count + 1, action="run_tests", reward=0.00, done=True, error="step_limit_reached")
            break
        res.raise_for_status()
        data   = res.json()
        state  = data["state"]
        reward = data["reward"]["value"] if isinstance(data["reward"], dict) else data["reward"]
        step_count += 1
        total_reward += reward
        all_rewards.append(reward)
        log_step(step=step_count, action="run_tests", reward=reward, done=state["done"])

        attempt += 1

    # grade final code
    res = requests.post(f"{BASE_URL}/grader/", json={"task_id": task_id, "code": state["code"]})
    res.raise_for_status()
    grade = res.json()

    score   = grade["score"]
    success = score == 1.0
    log_end(success=success, steps=step_count, score=score, rewards=all_rewards)

    return score, step_count, round(total_reward, 2)


# ── main ───────────────────────────────────────────────────────────
def main() -> None:
    if not API_KEY:
        print("ERROR: HF_TOKEN or API_KEY environment variable is not set.")
        sys.exit(1)
    if not MODEL_NAME:
        print("ERROR: MODEL_NAME environment variable is not set.")
        sys.exit(1)

    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    task_ids = ["easy", "medium", "hard"]
    results  = {}

    for i, task_id in enumerate(task_ids):
        session_id = f"inference-{task_id}-{i}"
        score, steps, reward = run_episode(client, task_id, session_id)
        results[task_id] = {"score": score, "steps": steps, "reward": reward}


if __name__ == "__main__":
    main()