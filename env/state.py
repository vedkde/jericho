from dataclasses import dataclass, field

@dataclass
class EnvState:
    code: str
    test_code: str
    last_test_output: str
    tests_passed: int
    tests_total: int
    step_count: int
    done: bool

    def copy(self):
        return EnvState(
            code=self.code,
            test_code=self.test_code,
            last_test_output=self.last_test_output,
            tests_passed=self.tests_passed,
            tests_total=self.tests_total,
            step_count=self.step_count,
            done=self.done
        )