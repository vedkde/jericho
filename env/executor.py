import subprocess
import tempfile
import os
import re

TIMEOUT_SECONDS = 10

class Executor:
    def run(self, code: str, test_code: str) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            solution_path = os.path.join(tmpdir, "solution.py")
            test_path = os.path.join(tmpdir, "test_solution.py")

            with open(solution_path, "w") as f:
                f.write(code)

            with open(test_path, "w") as f:
                f.write(test_code)

            return self._run_pytest(tmpdir, test_path)

    def _run_pytest(self, tmpdir: str, test_path: str) -> dict:
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", test_path, "-v", "--tb=short", "--no-header"],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                cwd=tmpdir
            )
            output = result.stdout + result.stderr
            passed, total = self._parse_results(output)

            return {
                "output": output,
                "passed": passed,
                "total": total,
                "timed_out": False
            }

        except subprocess.TimeoutExpired:
            return {
                "output": f"Execution timed out after {TIMEOUT_SECONDS} seconds.",
                "passed": 0,
                "total": 0,
                "timed_out": True
            }

        except Exception as e:
            return {
                "output": f"Executor error: {str(e)}",
                "passed": 0,
                "total": 0,
                "timed_out": False
            }

    def _parse_results(self, output: str) -> tuple:
        # look for pytest summary line e.g. "3 passed, 1 failed" or "2 passed"
        passed = 0
        total = 0

        passed_match = re.search(r"(\d+) passed", output)
        failed_match = re.search(r"(\d+) failed", output)
        error_match = re.search(r"(\d+) error", output)

        if passed_match:
            passed = int(passed_match.group(1))

        failed = int(failed_match.group(1)) if failed_match else 0
        errors = int(error_match.group(1)) if error_match else 0

        total = passed + failed + errors

        return passed, total