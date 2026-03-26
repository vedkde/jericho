import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
import time
from groq import Groq

BASE_URL = "http://localhost:8000"
GROQ_API_KEY = "key here"

client = Groq(api_key=GROQ_API_KEY)

DIVIDER     = "─" * 60
THIN        = "·" * 60
BOLD        = "═" * 60

def header(text):
    print(f"\n{BOLD}")
    print(f"  {text}")
    print(BOLD)

def subheader(text):
    print(f"\n{DIVIDER}")
    print(f"  {text}")
    print(DIVIDER)

def row(label, value, indent=2):
    pad = " " * indent
    print(f"{pad}{label:<22} {value}")

def progress_bar(passed, total, width=24):
    if total == 0:
        return "[" + " " * width + "]  0/0"
    filled = int(width * passed / total)
    empty  = width - filled
    bar    = "█" * filled + "░" * empty
    pct    = int(100 * passed / total)
    return f"[{bar}]  {passed}/{total}  ({pct}%)"

def result_label(passed, total):
    if passed == total:
        return "SOLVED"
    elif passed == 0:
        return "FAILING"
    else:
        return f"PARTIAL  ({passed}/{total})"

def ask_groq(code, test_output, functions, attempt, extra_hint=""):
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
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a Python debugging assistant. Return only raw JSON."},
            {"role": "user",   "content": prompt}
        ],
        temperature=0.1,
        max_tokens=1024
    )
    raw = response.choices[0].message.content.strip()
    if "```" in raw:
        raw = "\n".join(l for l in raw.split("\n") if not l.strip().startswith("```")).strip()
    return json.loads(raw)


def run_episode(task_id, session_id):
    header(f"TASK  {task_id.upper()}")

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

    res = requests.post(f"{BASE_URL}/env/reset", json={"session_id": session_id, "task_id": task_id})
    res.raise_for_status()
    state = res.json()["state"]

    print(f"\n  {THIN}")
    print(f"  INITIAL STATE")
    print(f"  {THIN}")
    row("Status",   progress_bar(state["tests_passed"], state["tests_total"]))

    total_reward   = 0.0
    attempt        = 1
    tried_functions = {}
    attempt_log    = []

    res = requests.post(f"{BASE_URL}/env/step", json={"session_id": session_id, "action": {"type": "run_tests"}})
    res.raise_for_status()
    data  = res.json()
    state = data["state"]
    total_reward += data["reward"]

    row("Tests",      progress_bar(state["tests_passed"], state["tests_total"]))
    row("Reward",     f"{data['reward']:+.2f}")

    print(f"\n  {THIN}")
    print(f"  AGENT LOOP")
    print(f"  {THIN}")

    while not state["done"]:
        stuck_hint = ""
        stuck = [f for f, c in tried_functions.items() if c >= 2]
        if stuck:
            stuck_hint = (
                f"\nWARNING: You already tried fixing {stuck} multiple times with no progress. "
                f"You MUST target a completely different function."
            )

        fix = ask_groq(
            code=state["code"],
            test_output=state["last_test_output"],
            functions=functions,
            attempt=attempt,
            extra_hint=stuck_hint
        )

        fn       = fix["function_name"]
        new_code = fix["new_code"]
        tried_functions[fn] = tried_functions.get(fn, 0) + 1

        print(f"\n  Attempt {attempt}")
        row("Targeting",  fn)
        row("Times tried", f"{tried_functions[fn]}x")
        row("Fix preview", new_code.split("\n")[0][:52].strip())

        res = requests.post(f"{BASE_URL}/env/step", json={
            "session_id": session_id,
            "action": {"type": "edit_function", "function_name": fn, "new_code": new_code}
        })
        if res.status_code == 400:
            print(f"\n  [step limit reached]")
            break
        res.raise_for_status()
        data  = res.json()
        state = data["state"]
        total_reward += data["reward"]

        if state["done"]:
            break

        res = requests.post(f"{BASE_URL}/env/step", json={
            "session_id": session_id,
            "action": {"type": "run_tests"}
        })
        if res.status_code == 400:
            print(f"\n  [step limit reached]")
            break
        res.raise_for_status()
        data  = res.json()
        state = data["state"]
        total_reward += data["reward"]

        status = result_label(state["tests_passed"], state["tests_total"])
        row("Result",    progress_bar(state["tests_passed"], state["tests_total"]))
        row("Reward",    f"{data['reward']:+.2f}")
        row("Status",    status)

        attempt_log.append({
            "attempt":  attempt,
            "function": fn,
            "passed":   state["tests_passed"],
            "total":    state["tests_total"],
            "reward":   data["reward"]
        })

        attempt += 1

    print(f"\n  {THIN}")
    print(f"  GRADING")
    print(f"  {THIN}")

    res = requests.post(f"{BASE_URL}/grader/", json={"task_id": task_id, "code": state["code"]})
    res.raise_for_status()
    grade = res.json()

    row("Final score",   f"{grade['score']:.2f}  ({grade['passed']}/{grade['total']} tests)")
    row("Total reward",  f"{round(total_reward, 2):+.2f}")
    row("Attempts used", str(attempt - 1))
    row("Outcome",       "PASSED" if grade["score"] == 1.0 else "INCOMPLETE")

    return grade["score"], attempt - 1, round(total_reward, 2)


def main():
    start = time.time()

    header("DEBUGGING ENVIRONMENT  —  AGENT RUN")
    print(f"\n  Model     : llama-3.3-70b-versatile  (Groq)")
    print(f"  Tasks     : easy  /  medium  /  hard")
    print(f"  Max steps : 20 per episode\n")

    task_ids = ["easy", "medium", "hard"]
    results  = {}

    for i, task_id in enumerate(task_ids):
        session_id = f"groq-{task_id}-{i}"
        score, attempts, reward = run_episode(task_id, session_id)
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