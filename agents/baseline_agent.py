import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#groq key: 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
import requests
import json

BASE_URL = "http://localhost:8000"

def section(title):
    print("\n" + "="*50)
    print(f"  {title}")
    print("="*50)

def print_state(state: dict):
    print(f"  step        : {state['step_count']}")
    print(f"  tests passed: {state['tests_passed']} / {state['tests_total']}")
    print(f"  done        : {state['done']}")

def run_episode(task_id: str, session_id: str):
    section(f"TASK: {task_id.upper()} | session: {session_id}")

    # ── reset ──────────────────────────────────────
    res = requests.post(f"{BASE_URL}/env/reset", json={
        "session_id": session_id,
        "task_id": task_id
    })
    res.raise_for_status()
    data = res.json()
    state = data["state"]
    print(f"\n  reset done — loaded buggy code")
    print_state(state)

    # ── step 1: run tests on buggy code ────────────
    print("\n  [step 1] running tests on buggy code...")
    res = requests.post(f"{BASE_URL}/env/step", json={
        "session_id": session_id,
        "action": {"type": "run_tests"}
    })
    res.raise_for_status()
    data = res.json()
    state = data["state"]
    print_state(state)
    print(f"  reward: {data['reward']}")

    # ── step 2: apply solution ──────────────────────
    print("\n  [step 2] applying solution fix...")
    task_res = requests.get(f"{BASE_URL}/tasks/{task_id}")
    task_res.raise_for_status()
    task_data = task_res.json()

    # get solution from grader endpoint by task_id
    from tasks.registry import get_task
    task = get_task(task_id)
    solution_code = task["solution_code"]

    res = requests.post(f"{BASE_URL}/env/step", json={
        "session_id": session_id,
        "action": {
            "type": "edit",
            "new_code": solution_code
        }
    })
    res.raise_for_status()
    data = res.json()
    state = data["state"]
    print_state(state)
    print(f"  reward: {data['reward']}")

    # ── step 3: run tests on fixed code ────────────
    print("\n  [step 3] running tests on fixed code...")
    res = requests.post(f"{BASE_URL}/env/step", json={
        "session_id": session_id,
        "action": {"type": "run_tests"}
    })
    res.raise_for_status()
    data = res.json()
    state = data["state"]
    print_state(state)
    print(f"  reward: {data['reward']}")
    print(f"  done  : {data['done']}")

    # ── grader ─────────────────────────────────────
    print("\n  [grader] evaluating final code...")
    res = requests.post(f"{BASE_URL}/grader/", json={
        "task_id": task_id,
        "code": solution_code
    })
    res.raise_for_status()
    grade = res.json()
    print(f"  score : {grade['score']} ({grade['passed']}/{grade['total']} tests)")

    return grade["score"]

def main():
    task_ids = ["easy", "medium", "hard"]
    scores = {}

    for i, task_id in enumerate(task_ids):
        session_id = f"baseline-{task_id}-{i}"
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