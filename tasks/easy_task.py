EASY_TASK = {
    "task_id": "easy",
    "difficulty": "easy",
    "description": "Fix a discount calculator — wrong operator in apply_discount, and compute_final ignores the discount entirely.",
    "total_tests": 4,
    "functions": ["apply_discount", "compute_final"],

    "buggy_code": """\
def apply_discount(price, percent):
    discount = price * percent * 100
    return round(discount, 2)

def compute_final(price, percent):
    return round(price, 2)
""",

    "solution_code": """\
def apply_discount(price, percent):
    discount = price * percent / 100
    return round(discount, 2)

def compute_final(price, percent):
    discount = apply_discount(price, percent)
    return round(price - discount, 2)
""",

    "test_code": """\
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from solution import apply_discount, compute_final

def test_discount_basic():
    assert apply_discount(100, 10) == 10.0

def test_discount_small():
    assert apply_discount(200, 5) == 10.0

def test_final_basic():
    assert compute_final(100, 10) == 90.0

def test_final_no_discount():
    assert compute_final(50, 0) == 50.0
"""
}