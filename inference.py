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

# ── display helpers ────────────────────────────────────────────────
DIVIDER = "─" * 60
THIN    = "·" * 60
BOLD    = "═" * 60

def header(text):
    print(f"\n{BOLD}\n  {text}\n{BOLD}")

def subheader(text):
    print(f"\n{DIVIDER}\n  {text}\n{DIVIDER}")

def row(label, value, indent=2):
    print(f"{' ' * indent}{label:<22} {value}")

def progress_bar(passed, total, width=24):
    if total == 0:
        return "[" + " " * width + "]  0/0"
    filled = int(width * passed / total)
    bar    = "█" * filled + "░" * (width - filled)
    pct    = int(100 * passed / total)
    return f"[{bar}]  {passed}/{total}  ({pct}%)"

def result_label(passed, total):
    if passed == total:
        return "SOLVED"
    elif passed == 0:
        return "FAILING"
    else:
        return f"PARTIAL  ({passed}/{total})"


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
    header(f"TASK  {task_id.upper()}")

    # fetch task metadata
    task_res = requests.get(f"{BASE_URL}/tasks/{task_id}")
    task_res.raise_for_status()
    task_data  = task_res.json()
    functions  = task_data.get("functions", [])
    difficulty = task_data.get("difficulty", task_id)
    desc       = task_data.get("description", "")

    print(f"\n  {desc}\n")
    row("Difficulty",  difficulty.upper())
    row("Functions",   ", ".join(functions))
    row("Total tests", str(task_data.get("total_tests", "?")))

    # reset environment
    res = requests.post(f"{BASE_URL}/env/reset", json={"session_id": session_id, "task_id": task_id})
    res.raise_for_status()
    state = res.json()["state"]

    print(f"\n  {THIN}\n  INITIAL STATE\n  {THIN}")
    row("Status", progress_bar(state["tests_passed"], state["tests_total"]))

    total_reward    = 0.0
    attempt         = 1
    tried_functions = {}

    # initial test run
    res = requests.post(f"{BASE_URL}/env/step", json={"session_id": session_id, "action": {"type": "run_tests"}})
    res.raise_for_status()
    data   = res.json()
    state  = data["state"]
    reward = data["reward"]["value"] if isinstance(data["reward"], dict) else data["reward"]
    total_reward += reward

    row("Tests",  progress_bar(state["tests_passed"], state["tests_total"]))
    row("Reward", f"{reward:+.2f}")

    print(f"\n  {THIN}\n  AGENT LOOP\n  {THIN}")

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
        except Exception as exc:
            print(f"\n  [model error] {exc} — stopping episode.")
            break

        fn       = fix["function_name"]
        new_code = fix["new_code"]
        tried_functions[fn] = tried_functions.get(fn, 0) + 1

        print(f"\n  Attempt {attempt}")
        row("Targeting",   fn)
        row("Times tried", f"{tried_functions[fn]}x")
        row("Fix preview", new_code.split("\n")[0][:52].strip())

        # apply fix
        res = requests.post(f"{BASE_URL}/env/step", json={
            "session_id": session_id,
            "action": {"type": "edit_function", "function_name": fn, "new_code": new_code}
        })
        if res.status_code == 400:
            print(f"\n  [step limit reached]")
            break
        res.raise_for_status()
        data   = res.json()
        state  = data["state"]
        reward = data["reward"]["value"] if isinstance(data["reward"], dict) else data["reward"]
        total_reward += reward

        if state["done"]:
            break

        # run tests after fix
        res = requests.post(f"{BASE_URL}/env/step", json={
            "session_id": session_id,
            "action": {"type": "run_tests"}
        })
        if res.status_code == 400:
            print(f"\n  [step limit reached]")
            break
        res.raise_for_status()
        data   = res.json()
        state  = data["state"]
        reward = data["reward"]["value"] if isinstance(data["reward"], dict) else data["reward"]
        total_reward += reward

        row("Result",  progress_bar(state["tests_passed"], state["tests_total"]))
        row("Reward",  f"{reward:+.2f}")
        row("Status",  result_label(state["tests_passed"], state["tests_total"]))

        attempt += 1

    # grade final code
    print(f"\n  {THIN}\n  GRADING\n  {THIN}")
    res = requests.post(f"{BASE_URL}/grader/", json={"task_id": task_id, "code": state["code"]})
    res.raise_for_status()
    grade = res.json()

    row("Final score",   f"{grade['score']:.2f}  ({grade['passed']}/{grade['total']} tests)")
    row("Total reward",  f"{round(total_reward, 2):+.2f}")
    row("Attempts used", str(attempt - 1))
    row("Outcome",       "PASSED" if grade["score"] == 1.0 else "INCOMPLETE")

    return grade["score"], attempt - 1, round(total_reward, 2)


# ── main ───────────────────────────────────────────────────────────
def main() -> None:
    if not API_KEY:
        print("ERROR: HF_TOKEN or API_KEY environment variable is not set.")
        sys.exit(1)
    if not MODEL_NAME:
        print("ERROR: MODEL_NAME environment variable is not set.")
        sys.exit(1)

    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    start = time.time()

    header("CODE DEBUGGING AGENT — INFERENCE RUN")
    print(f"\n  Model     : {MODEL_NAME}")
    print(f"  API base  : {API_BASE_URL}")
    print(f"  Tasks     : easy  /  medium  /  hard")
    print(f"  Max steps : 20 per episode\n")

    task_ids = ["easy", "medium", "hard"]
    results  = {}

    for i, task_id in enumerate(task_ids):
        session_id = f"inference-{task_id}-{i}"
        score, attempts, reward = run_episode(client, task_id, session_id)
        results[task_id] = {"score": score, "attempts": attempts, "reward": reward}

    elapsed = round(time.time() - start, 1)

    header("FINAL RESULTS")
    print(f"\n  {'TASK':<12} {'SCORE':<10} {'ATTEMPTS':<12} {'REWARD':<12} {'OUTCOME'}")
    print(f"  {DIVIDER}")

    total_score = 0.0
    for task_id, r in results.items():
        outcome = "PASSED" if r["score"] == 1.0 else "INCOMPLETE"
        print(f"  {task_id:<12} {r['score']:<10.2f} {r['attempts']:<12} {r['reward']:<12.2f} {outcome}")
        total_score += r["score"]

    avg = total_score / len(results)
    print(f"  {THIN}")
    print(f"  {'AVERAGE':<12} {avg:<10.2f}")
    print(f"\n  Total runtime : {elapsed}s")
    print(f"\n{BOLD}\n")


if __name__ == "__main__":
    main()