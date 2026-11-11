"""Test 3 commands from docs/manager-commands.md, end to end without Claude.

Each case takes the doc's expected changes, applies them to the sample week,
re-solves, and checks every change holds in the new schedule. This proves the
expected answers are solvable; whether Claude produces them is Test 3 itself.
"""

from datetime import date

import pytest

from fair_schedule.changes import AssignShift, BlockShift, SetCoverage, SetMaxShifts, apply_changes
from fair_schedule.sample_data import sample_employees, sample_shifts
from fair_schedule.solver import solve_week

WEEK = date(2026, 11, 9)

CASES = {
    "1 give Sam Friday off": [
        BlockShift("sam", "fri-dinner-server"),
        BlockShift("sam", "fri-dinner-bar"),
    ],
    "2 Alex called out Saturday": [
        BlockShift("alex", "sat-brunch-server"),
        BlockShift("alex", "sat-dinner-server"),
    ],
    "3 Riley can't do Sunday brunch": [
        BlockShift("riley", "sun-brunch-bar"),
    ],
    "4 one more server Friday": [
        SetCoverage("fri-dinner-server", 4),
    ],
    "5 only one server Monday": [
        SetCoverage("mon-dinner-server", 1),
    ],
    "6 Taylor on Thursday bar": [
        AssignShift("taylor", "thu-dinner-bar"),
    ],
    "7 Taylor only 2 shifts": [
        SetMaxShifts("taylor", 2),
    ],
    "8 swap Bea's Tuesday with Dana": [
        BlockShift("bea", "tue-dinner-server"),
        AssignShift("dana", "tue-dinner-server"),
    ],
    "9 Eli sick Tuesday, extra bartender Thursday": [
        BlockShift("eli", "tue-dinner-server"),
        SetCoverage("thu-dinner-bar", 2),
    ],
}


@pytest.mark.parametrize("changes", CASES.values(), ids=CASES.keys())
def test_command_changes_hold_in_the_resolved_schedule(changes):
    shifts, employees = sample_shifts(), sample_employees()
    week = apply_changes(shifts, employees, changes)

    schedule = solve_week(
        week.shifts, week.employees, {e.id: 0 for e in employees}, WEEK, required=week.required
    )

    worked = {(a.employee_id, a.shift_id) for a in schedule.assignments}
    for change in changes:
        match change:
            case BlockShift(employee_id, shift_id):
                assert (employee_id, shift_id) not in worked
            case AssignShift(employee_id, shift_id):
                assert (employee_id, shift_id) in worked
            case SetCoverage(shift_id, needed):
                assert sum(s == shift_id for _, s in worked) == needed
            case SetMaxShifts(employee_id, max_shifts):
                assert sum(e == employee_id for e, _ in worked) <= max_shifts
