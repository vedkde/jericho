import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from google import genai

BASE_URL = "http://localhost:8000"
GEMINI_API_KEY = "key here"

client = genai.Client(api_key=GEMINI_API_KEY)

def section(title):
    print("\n" + "="*50)
    print(f"  {title}")
    print("="*50)

def ask_gemini(buggy_code: str, test_output: str, attempt: int) -> str:
    prompt = f"""You are a Python debugging assistant.

You are given buggy Python code and the output from running its tests.
Your job is to fix the code so all tests pass.

ATTEMPT: {attempt}

CURRENT CODE:
{buggy_code}

TEST OUTPUT:
{test_output}

Instructions:
- Return ONLY the fixed Python code
- Do NOT include any explanation
- Do NOT include markdown code fences
- Do NOT include ```python or ```
- Just return the raw fixed code only
"""
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=prompt
    )
    return response.text.strip()

def run_episode(task_id: str, session_id: str):
    section(f"TASK: {task_id.upper()} | session: {session_id}")

    # ── reset ──────────────────────────────────────
    res = requests.post(f"{BASE_URL}/env/reset", json={
        "session_id": session_id,
        "task_id": task_id
    })
    res.raise_for_status()
    state = res.json()["state"]
    print(f"\n  reset done — loaded buggy code")
    print(f"  tests passed: {state['tests_passed']} / {state['tests_total']}")

    total_reward = 0.0
    attempt = 1

    # ── run tests first to see failures ────────────
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
    print(f"  test output :\n{state['last_test_output'].strip()}")

    # ── agent loop ─────────────────────────────────
    while not state["done"]:
        print(f"\n  [attempt {attempt}] asking Gemini to fix the code...")

        fixed_code = ask_gemini(
            buggy_code=state["code"],
            test_output=state["last_test_output"],
            attempt=attempt
        )

        print(f"  Gemini returned fix ({len(fixed_code)} chars)")
        print(f"  fix preview: {fixed_code[:80].strip()}...")

        # apply edit
        res = requests.post(f"{BASE_URL}/env/step", json={
            "session_id": session_id,
            "action": {
                "type": "edit",
                "new_code": fixed_code
            }
        })
        res.raise_for_status()
        data = res.json()
        state = data["state"]
        total_reward += data["reward"]

        # run tests
        res = requests.post(f"{BASE_URL}/env/step", json={
            "session_id": session_id,
            "action": {"type": "run_tests"}
        })
        res.raise_for_status()
        data = res.json()
        state = data["state"]
        total_reward += data["reward"]

        print(f"  tests passed: {state['tests_passed']} / {state['tests_total']}")
        print(f"  reward      : {data['reward']}")
        print(f"  done        : {state['done']}")

        attempt += 1

    # ── grader ─────────────────────────────────────
    print(f"\n  [grader] evaluating final code...")
    res = requests.post(f"{BASE_URL}/grader/", json={
        "task_id": task_id,
        "code": state["code"]
    })
    res.raise_for_status()
    grade = res.json()

    print(f"  score       : {grade['score']} ({grade['passed']}/{grade['total']} tests)")
    print(f"  total reward: {round(total_reward, 4)}")
    print(f"  attempts    : {attempt - 1}")

    return grade["score"]

def main():
    task_ids = ["easy", "medium", "hard"]
    scores = {}

    for i, task_id in enumerate(task_ids):
        session_id = f"gemini-{task_id}-{i}"
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