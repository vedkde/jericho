HARD_TASK = {
    "task_id": "hard",
    "difficulty": "hard",
    "description": "Fix a payroll pipeline where multiple functions each contain multiple bugs. Tests give no hints. Bugs cascade and interact across functions.",
    "total_tests": 10,
    "functions": ["parse_employees", "compute_tax", "compute_bonus", "compute_net", "generate_payslips"],

    "buggy_code": """\
def parse_employees(raw):
    employees = []
    for emp in raw:
        salary = int(emp["salary"])
        hours = int(emp["hours_worked"])
        employees.append({
            "id": emp["id"],
            "name": emp["name"].strip().lower(),
            "department": emp["department"].strip().lower(),
            "salary": salary,
            "hours_worked": hours,
            "overtime_hours": max(0, hours - 160),
            "hourly_rate": salary / 160,
            "performance": emp["performance"].strip().lower(),
            "region": emp.get("region", "domestic")
        })
    return employees


def compute_tax(employees):
    result = []
    for emp in employees:
        salary = emp["salary"]
        region = emp["region"]

        if salary < 30000:
            rate = 0.10
        elif salary < 60000:
            rate = 0.20
        elif salary < 100000:
            rate = 0.30
        else:
            rate = 0.40

        if region == "international":
            rate = rate + 0.05

        emp["tax_rate"] = rate
        emp["tax"] = int(salary * rate)
        result.append(emp)
    return result


def compute_bonus(employees):
    result = []
    for emp in employees:
        salary = emp["salary"]
        perf = emp["performance"]
        overtime = emp["overtime_hours"]
        hourly = emp["hourly_rate"]

        if perf == "excellent":
            bonus_rate = 0.20
        elif perf == "good":
            bonus_rate = 0.10
        elif perf == "average":
            bonus_rate = 0.05
        else:
            bonus_rate = 0.0

        performance_bonus = round(salary * bonus_rate, 2)
        overtime_pay = round(overtime * hourly * 2.0, 2)

        emp["bonus"] = performance_bonus
        emp["overtime_pay"] = overtime_pay
        result.append(emp)
    return result


def compute_net(employees):
    result = []
    for emp in employees:
        gross = emp["salary"] + emp["bonus"] + emp["overtime_pay"]
        net = gross - emp["tax"] - emp["bonus"]
        emp["gross"] = round(gross, 2)
        emp["net"] = round(net, 2)
        result.append(emp)
    return result


def generate_payslips(employees):
    payslips = []
    total_net = 0
    for emp in employees:
        total_net += emp["net"]
        payslips.append({
            "id": emp["id"],
            "name": emp["name"],
            "department": emp["department"],
            "gross": emp["gross"],
            "tax": emp["tax"],
            "net": emp["net"],
            "bonus": emp["bonus"],
            "overtime_pay": emp["overtime_pay"],
            "take_home": emp["net"],
            "summary": f"{emp['name']} | {emp['department']} | gross={emp['gross']} tax={emp['tax']} net={emp['net']}"
        })
    payslips.append({"total_net": round(total_net, 2)})
    return payslips
""",

    "solution_code": """\
def parse_employees(raw):
    employees = []
    for emp in raw:
        salary = float(emp["salary"])
        hours = int(emp["hours_worked"])
        employees.append({
            "id": emp["id"],
            "name": emp["name"].strip().title(),
            "department": emp["department"].strip().upper(),
            "salary": salary,
            "hours_worked": hours,
            "overtime_hours": max(0, hours - 160),
            "hourly_rate": salary / 160,
            "performance": emp["performance"].strip().lower(),
            "region": emp.get("region", "domestic")
        })
    return employees


def compute_tax(employees):
    result = []
    for emp in employees:
        salary = emp["salary"]
        region = emp["region"]

        if salary <= 30000:
            rate = 0.10
        elif salary <= 60000:
            rate = 0.20
        elif salary <= 100000:
            rate = 0.30
        else:
            rate = 0.40

        if region == "international":
            rate = rate + 0.05

        emp["tax_rate"] = rate
        emp["tax"] = round(salary * rate, 2)
        result.append(emp)
    return result


def compute_bonus(employees):
    result = []
    for emp in employees:
        salary = emp["salary"]
        perf = emp["performance"]
        overtime = emp["overtime_hours"]
        hourly = emp["hourly_rate"]

        if perf == "excellent":
            bonus_rate = 0.20
        elif perf == "good":
            bonus_rate = 0.10
        elif perf == "average":
            bonus_rate = 0.05
        else:
            bonus_rate = 0.0

        performance_bonus = round(salary * bonus_rate, 2)
        overtime_pay = round(overtime * hourly * 1.5, 2)

        emp["bonus"] = performance_bonus
        emp["overtime_pay"] = overtime_pay
        result.append(emp)
    return result


def compute_net(employees):
    result = []
    for emp in employees:
        gross = emp["salary"] + emp["bonus"] + emp["overtime_pay"]
        net = gross - emp["tax"]
        emp["gross"] = round(gross, 2)
        emp["net"] = round(net, 2)
        result.append(emp)
    return result


def generate_payslips(employees):
    payslips = []
    total_net = 0
    for emp in employees:
        total_net += emp["net"]
        payslips.append({
            "id": emp["id"],
            "name": emp["name"],
            "department": emp["department"],
            "gross": emp["gross"],
            "tax": emp["tax"],
            "net": emp["net"],
            "bonus": emp["bonus"],
            "overtime_pay": emp["overtime_pay"],
            "take_home": emp["net"],
            "summary": f"{emp['name']} | {emp['department']} | gross={emp['gross']} tax={emp['tax']} net={emp['net']}"
        })
    payslips.append({"total_net": round(total_net, 2)})
    return payslips
""",

    "test_code": """\
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from solution import parse_employees, compute_tax, compute_bonus, compute_net, generate_payslips

RAW = [
    {
        "id": "E001",
        "name": "  alice johnson  ",
        "department": "  engineering  ",
        "salary": "90000",
        "hours_worked": "180",
        "performance": "excellent",
        "region": "domestic"
    },
    {
        "id": "E002",
        "name": "bob smith",
        "department": "SALES",
        "salary": "45000",
        "hours_worked": "160",
        "performance": "good",
        "region": "international"
    },
    {
        "id": "E003",
        "name": "carol white",
        "department": "hr",
        "salary": "30000",
        "hours_worked": "200",
        "performance": "average",
        "region": "domestic"
    },
    {
        "id": "E004",
        "name": "dave brown",
        "department": "engineering",
        "salary": "120000",
        "hours_worked": "155",
        "performance": "poor",
        "region": "international"
    },
]


def _run_pipeline(raw=RAW):
    emps = parse_employees(raw)
    emps = compute_tax(emps)
    emps = compute_bonus(emps)
    emps = compute_net(emps)
    return emps


# ── stage 1 ────────────────────────────────────────────────────────

def test_stage1_a():
    emps = parse_employees(RAW)
    alice = next(e for e in emps if e["id"] == "E001")
    assert alice["name"] == "Alice Johnson", f"got {alice['name']}"
    assert alice["department"] == "ENGINEERING", f"got {alice['department']}"

def test_stage1_b():
    emps = parse_employees(RAW)
    alice = next(e for e in emps if e["id"] == "E001")
    assert alice["salary"] == 90000.0
    assert alice["overtime_hours"] == 20
    assert round(alice["hourly_rate"], 4) == round(90000.0 / 160, 4)


# ── stage 2 ────────────────────────────────────────────────────────

def test_stage2_a():
    emps = parse_employees(RAW)
    emps = compute_tax(emps)
    carol = next(e for e in emps if e["id"] == "E003")
    # salary == 30000 exactly → must hit <= 30000 bracket → 10%
    assert carol["tax_rate"] == 0.10, f"got {carol['tax_rate']}"
    assert carol["tax"] == round(30000 * 0.10, 2), f"got {carol['tax']}"

def test_stage2_b():
    emps = parse_employees(RAW)
    emps = compute_tax(emps)
    bob = next(e for e in emps if e["id"] == "E002")
    # international + 20% bracket = 25%
    assert bob["tax_rate"] == 0.25, f"got {bob['tax_rate']}"
    assert bob["tax"] == round(45000 * 0.25, 2), f"got {bob['tax']}"


# ── stage 3 ────────────────────────────────────────────────────────

def test_stage3_a():
    emps = parse_employees(RAW)
    emps = compute_tax(emps)
    emps = compute_bonus(emps)
    alice = next(e for e in emps if e["id"] == "E001")
    assert alice["bonus"] == round(90000 * 0.20, 2)
    expected_ot = round(20 * (90000.0 / 160) * 1.5, 2)
    assert alice["overtime_pay"] == expected_ot, f"got {alice['overtime_pay']} expected {expected_ot}"

def test_stage3_b():
    emps = parse_employees(RAW)
    emps = compute_tax(emps)
    emps = compute_bonus(emps)
    bob = next(e for e in emps if e["id"] == "E002")
    assert bob["overtime_pay"] == 0.0
    assert bob["bonus"] == round(45000 * 0.10, 2)


# ── stage 4 ────────────────────────────────────────────────────────

def test_stage4_a():
    emps = _run_pipeline()
    alice = next(e for e in emps if e["id"] == "E001")
    expected_gross = round(90000 + alice["bonus"] + alice["overtime_pay"], 2)
    expected_net = round(expected_gross - alice["tax"], 2)
    assert alice["gross"] == expected_gross, f"got {alice['gross']}"
    assert alice["net"] == expected_net, f"got {alice['net']}"

def test_stage4_b():
    emps = _run_pipeline()
    dave = next(e for e in emps if e["id"] == "E004")
    assert dave["gross"] == round(120000 + 0 + 0, 2)
    expected_net = round(dave["gross"] - dave["tax"], 2)
    assert dave["net"] == expected_net, f"got {dave['net']} expected {expected_net}"


# ── stage 5 ────────────────────────────────────────────────────────

def test_stage5_a():
    emps = _run_pipeline()
    slips = generate_payslips(emps)
    alice_slip = next(p for p in slips if p.get("id") == "E001")
    assert alice_slip["take_home"] == alice_slip["net"]
    assert "Alice Johnson" in alice_slip["summary"]
    assert "ENGINEERING" in alice_slip["summary"]

def test_stage5_b():
    emps = _run_pipeline()
    slips = generate_payslips(emps)
    total = next(p for p in slips if "total_net" in p)
    expected = round(sum(e["net"] for e in emps), 2)
    assert total["total_net"] == expected, f"got {total['total_net']} expected {expected}"
"""
}