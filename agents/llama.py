import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from groq import Groq

BASE_URL = "http://localhost:8000"
GROQ_API_KEY = "key here"

client = Groq(api_key=GROQ_API_KEY)

def section(title):
    print("\n" + "="*50)
    print(f"  {title}")
    print("="*50)

def ask_groq(code: str, test_output: str, functions: list, attempt: int, extra_hint: str = "") -> dict:
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

Example response format:
{{"function_name": "compute_total", "new_code": "def compute_total(x, y):\\n    return x + y"}}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a Python debugging assistant. You return only raw JSON, no explanation, no markdown."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.1,
        max_tokens=1024
    )

    raw = response.choices[0].message.content.strip()

    # strip markdown fences if model ignores instructions
    if "```" in raw:
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines).strip()

    parsed = json.loads(raw)
    return parsed


def run_episode(task_id: str, session_id: str):
    section(f"TASK: {task_id.upper()} | session: {session_id}")

    # ── get task metadata ──────────────────────────
    task_res = requests.get(f"{BASE_URL}/tasks/{task_id}")
    task_res.raise_for_status()
    task_data = task_res.json()
    functions = task_data.get("functions", [])

    # ── reset ──────────────────────────────────────
    res = requests.post(f"{BASE_URL}/env/reset", json={
        "session_id": session_id,
        "task_id": task_id
    })
    res.raise_for_status()
    state = res.json()["state"]
    print(f"\n  reset done — loaded buggy code")
    print(f"  functions   : {functions}")
    print(f"  tests passed: {state['tests_passed']} / {state['tests_total']}")

    total_reward = 0.0
    attempt = 1
    tried_functions = {}  # tracks how many times each function was attempted

    # ── initial test run ───────────────────────────
    res = requests.post(f"{BASE_URL}/env/step", json={
        "session_id": session_id,
        "action": {"type": "run_tests"}
    })
    res.raise_for_status()
    data = res.json()
    state = data["state"]
    total_reward += data["reward"]
    print(f"\n  [initial test run]")
    print(f"  tests passed: {state['tests_passed']} / {state['tests_total']}")

    # ── agent loop ─────────────────────────────────
    while not state["done"]:
        print(f"\n  [attempt {attempt}] asking Groq which function to fix...")

        # build hint if model is stuck on same function
        stuck_hint = ""
        stuck = [f for f, c in tried_functions.items() if c >= 2]
        if stuck:
            stuck_hint = (
                f"\nWARNING: You have already tried fixing these functions "
                f"multiple times with no progress: {stuck}. "
                f"You MUST try a completely different function this time."
            )

        fix = ask_groq(
            code=state["code"],
            test_output=state["last_test_output"],
            functions=functions,
            attempt=attempt,
            extra_hint=stuck_hint
        )

        function_name = fix["function_name"]
        new_code = fix["new_code"]
        tried_functions[function_name] = tried_functions.get(function_name, 0) + 1

        print(f"  Groq targeting : {function_name} (tried {tried_functions[function_name]}x)")
        print(f"  fix preview    : {new_code[:80].strip()}...")

        # apply function edit
        res = requests.post(f"{BASE_URL}/env/step", json={
            "session_id": session_id,
            "action": {
                "type": "edit_function",
                "function_name": function_name,
                "new_code": new_code
            }
        })
        if res.status_code == 400:
            print("  episode ended by step limit")
            break
        res.raise_for_status()
        data = res.json()
        state = data["state"]
        total_reward += data["reward"]

        if state["done"]:
            print(f"  tests passed   : {state['tests_passed']} / {state['tests_total']}")
            break

        # run tests
        res = requests.post(f"{BASE_URL}/env/step", json={
            "session_id": session_id,
            "action": {"type": "run_tests"}
        })
        if res.status_code == 400:
            print("  episode ended by step limit")
            break
        res.raise_for_status()
        data = res.json()
        state = data["state"]
        total_reward += data["reward"]

        print(f"  tests passed   : {state['tests_passed']} / {state['tests_total']}")
        print(f"  reward         : {data['reward']}")
        print(f"  done           : {state['done']}")

        attempt += 1

    # ── grader ─────────────────────────────────────
    print(f"\n  [grader] evaluating final code...")
    res = requests.post(f"{BASE_URL}/grader/", json={
        "task_id": task_id,
        "code": state["code"]
    })
    res.raise_for_status()
    grade = res.json()

    print(f"  score          : {grade['score']} ({grade['passed']}/{grade['total']} tests)")
    print(f"  total reward   : {round(total_reward, 4)}")
    print(f"  attempts       : {attempt - 1}")

    return grade["score"]


def main():
    task_ids = ["easy", "medium", "hard"]
    scores = {}

    for i, task_id in enumerate(task_ids):
        session_id = f"groq-{task_id}-{i}"
        score = run_episode(task_id, session_id)
        scores[task_id] = score

    section("FINAL SCORES")
    total = 0.0
    for task_id, score in scores.items():
        print(f"  {task_id:<10} → {score}")
        total += score
    avg = round(total / len(scores), 4)
    print(f"\n  average score: {avg}")


if __name__ == "__main__":
    main()