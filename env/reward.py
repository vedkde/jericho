from env.state import EnvState

STEP_PENALTY = -0.05
PROGRESS_REWARD = 1.0
REGRESSION_PENALTY = -0.5
ALL_PASS_BONUS = 2.0
BREAK_CODE_PENALTY = -0.3

def compute_reward(old_state: EnvState, new_state: EnvState) -> float:
    reward = 0.0

    # small penalty every step to encourage efficiency
    reward += STEP_PENALTY

    delta = new_state.tests_passed - old_state.tests_passed

    if delta > 0:
        # more tests passing than before
        reward += PROGRESS_REWARD * delta

    elif delta < 0:
        # broke something that was passing
        reward += REGRESSION_PENALTY * abs(delta)

    # if code couldn't even run (syntax error etc), extra penalty
    if new_state.tests_passed == 0 and "error" in new_state.last_test_output.lower():
        reward += BREAK_CODE_PENALTY

    # bonus for solving it completely
    if new_state.tests_passed == new_state.tests_total and new_state.tests_total > 0:
        reward += ALL_PASS_BONUS

    return round(reward, 4)