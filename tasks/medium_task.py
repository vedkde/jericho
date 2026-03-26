MEDIUM_TASK = {
    "task_id": "medium",
    "difficulty": "medium",
    "description": "Fix a stats calculator — mean divides wrong, variance uses wrong formula, std_dev calls wrong function.",
    "total_tests": 5,
    "functions": ["mean", "variance", "std_dev"],

    "buggy_code": """\
def mean(nums):
    if not nums:
        return 0
    return sum(nums) // len(nums)

def variance(nums):
    if not nums:
        return 0
    m = mean(nums)
    return sum((x + m) ** 2 for x in nums) / len(nums)

def std_dev(nums):
    return variance(nums) ** 2
""",

    "solution_code": """\
def mean(nums):
    if not nums:
        return 0
    return sum(nums) / len(nums)

def variance(nums):
    if not nums:
        return 0
    m = mean(nums)
    return sum((x - m) ** 2 for x in nums) / len(nums)

def std_dev(nums):
    return variance(nums) ** 0.5
""",

    "test_code": """\
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from solution import mean, variance, std_dev

def test_mean_basic():
    assert mean([1, 2, 3, 4, 5]) == 3.0

def test_mean_floats():
    assert mean([1, 2]) == 1.5

def test_variance_basic():
    assert variance([2, 4, 4, 4, 5, 5, 7, 9]) == 4.0

def test_std_dev_basic():
    assert std_dev([2, 4, 4, 4, 5, 5, 7, 9]) == 2.0

def test_std_dev_single():
    assert std_dev([5]) == 0.0
"""
}