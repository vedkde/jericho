import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env import DebugEnv
from tasks.registry import list_tasks

env = DebugEnv()

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def print_state(state):
    print(f"  step        : {state.step_count}")
    print(f"  tests passed: {state.tests_passed} / {state.tests_total}")
    print(f"  done        : {state.done}")
    print(f"  last output :\n{state.last_test_output.strip()}")
    print()

def section(title):
    print("\n" + "="*50)
    print(f"  {title}")
    print("="*50)

# ─────────────────────────────────────────
# TEST 1 — list tasks
# ─────────────────────────────────────────

section("TEST 1: list_tasks()")
tasks = list_tasks()
for t in tasks:
    print(f"  [{t['difficulty']}] {t['task_id']} — {t['description']}")
assert len(tasks) == 3, "Should have 3 tasks"
print("\n  PASSED")

# ─────────────────────────────────────────
# TEST 2 — reset loads buggy code
# ─────────────────────────────────────────

section("TEST 2: reset() loads buggy state")
state = env.reset("easy")
assert state.code is not None
assert state.tests_total == 4, f"Expected 4 tests for easy task, got {state.tests_total}"
assert state.step_count == 0
assert state.done == False
print(f"  code loaded  : {repr(state.code[:40])}...")
print(f"  tests_total  : {state.tests_total}")
print("\n  PASSED")

# ─────────────────────────────────────────
# TEST 3 — run tests on buggy code
# ─────────────────────────────────────────

section("TEST 3: run_tests on buggy code → should fail")
state, reward, done = env.step({"type": "run_tests"})
print_state(state)
assert state.tests_passed < state.tests_total, "Buggy code should not pass all tests"
assert reward < 0, f"Reward should be negative, got {reward}"
print(f"  reward: {reward}")
print("\n  PASSED")

# ─────────────────────────────────────────
# TEST 4 — edit_function then run tests
# ─────────────────────────────────────────

section("TEST 4: edit_function apply_discount fix → run tests")

fixed_apply_discount = """\
def apply_discount(price, percent):
    discount = price * percent / 100
    return round(discount, 2)
"""

state, reward, done = env.step({
    "type": "edit_function",
    "function_name": "apply_discount",
    "new_code": fixed_apply_discount
})
print(f"  after edit apply_discount — tests_passed: {state.tests_passed}")

state, reward, done = env.step({"type": "run_tests"})
print_state(state)
print(f"  reward: {reward}")
print("\n  PASSED")

# ─────────────────────────────────────────
# TEST 5 — fix second function, all tests pass
# ─────────────────────────────────────────

section("TEST 5: edit_function compute_final fix → all tests pass")

fixed_compute_final = """\
def compute_final(price, percent):
    discount = apply_discount(price, percent)
    return round(price - discount, 2)
"""

state, reward, done = env.step({
    "type": "edit_function",
    "function_name": "compute_final",
    "new_code": fixed_compute_final
})
print(f"  after edit compute_final — tests_passed: {state.tests_passed}")

state, reward, done = env.step({"type": "run_tests"})
print_state(state)
assert state.tests_passed == state.tests_total, "Fixed code should pass all tests"
assert done == True, "Episode should be done after all tests pass"
print(f"  reward: {reward}")
print("\n  PASSED")

# ─────────────────────────────────────────
# TEST 6 — state() returns current state
# ─────────────────────────────────────────

section("TEST 6: state() returns correct snapshot")
snapshot = env.state()
assert snapshot.done == True
assert snapshot.tests_passed == 4, f"Expected 4 tests passed, got {snapshot.tests_passed}"
print(f"  snapshot done        : {snapshot.done}")
print(f"  snapshot tests_passed: {snapshot.tests_passed}")
print("\n  PASSED")

# ─────────────────────────────────────────
# TEST 7 — step after done raises error
# ─────────────────────────────────────────

section("TEST 7: step() after done raises RuntimeError")
try:
    env.step({"type": "run_tests"})
    assert False, "Should have raised RuntimeError"
except RuntimeError as e:
    print(f"  caught expected error: {e}")
    print("\n  PASSED")

# ─────────────────────────────────────────
# TEST 8 — medium task loads and runs
# ─────────────────────────────────────────

section("TEST 8: medium task — reset and run buggy tests")
state = env.reset("medium")
assert state.tests_total == 5, f"Expected 5 tests for medium task, got {state.tests_total}"
state, reward, done = env.step({"type": "run_tests"})
print_state(state)
assert state.tests_passed < state.tests_total
print(f"  reward: {reward}")
print("\n  PASSED")

# ─────────────────────────────────────────
# TEST 9 — hard task loads and runs
# ─────────────────────────────────────────

section("TEST 9: hard task — reset and run buggy tests")
state = env.reset("hard")
assert state.tests_total == 10, f"Expected 10 tests for hard task, got {state.tests_total}"
state, reward, done = env.step({"type": "run_tests"})
print_state(state)
assert state.tests_passed < state.tests_total
print(f"  reward: {reward}")
print("\n  PASSED")

# ─────────────────────────────────────────
# TEST 10 — step limit ends episode
# ─────────────────────────────────────────

section("TEST 10: step limit — episode ends at MAX_STEPS")
state = env.reset("easy")
done = False
steps = 0
while not done:
    state, reward, done = env.step({"type": "run_tests"})
    steps += 1

assert done == True
print(f"  episode ended after {steps} steps")
print(f"  tests_passed: {state.tests_passed} / {state.tests_total}")
print("\n  PASSED")

# ─────────────────────────────────────────
# TEST 11 — unknown action raises error
# ─────────────────────────────────────────

section("TEST 11: unknown action type raises ValueError")
env.reset("easy")
try:
    env.step({"type": "fly_to_moon"})
    assert False, "Should have raised ValueError"
except ValueError as e:
    print(f"  caught expected error: {e}")
    print("\n  PASSED")

# ─────────────────────────────────────────
# DONE
# ─────────────────────────────────────────

section("ALL TESTS PASSED")