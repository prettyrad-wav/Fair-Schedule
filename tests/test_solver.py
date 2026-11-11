"""Tests for solve_week's required assignments (AssignShift)."""

from datetime import date

import pytest

from fair_schedule.models import Assignment
from fair_schedule.sample_data import sample_employees, sample_shifts
from fair_schedule.solver import solve_week

WEEK = date(2026, 11, 9)


def solve(required):
    employees = sample_employees()
    return solve_week(sample_shifts(), employees, {e.id: 0 for e in employees}, WEEK, required=required)


def test_required_assignment_is_in_the_schedule():
    # Without it, Riley works Thursday bar (see docs/manager-commands.md).
    schedule = solve({("taylor", "thu-dinner-bar")})

    assert Assignment("taylor", "thu-dinner-bar") in schedule.assignments


def test_impossible_required_assignment_fails_instead_of_being_dropped():
    # Taylor rated Monday bar Can't, so this can't be honored.
    with pytest.raises(ValueError):
        solve({("taylor", "mon-dinner-bar")})
