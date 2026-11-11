"""Tests for one-week manager changes (docs/manager-commands.md)."""

import pytest

from fair_schedule.changes import AssignShift, BlockShift, SetCoverage, SetMaxShifts, apply_changes
from fair_schedule.models import Rating
from fair_schedule.sample_data import sample_employees, sample_shifts


def employee(week, employee_id):
    return next(e for e in week.employees if e.id == employee_id)


def shift(week, shift_id):
    return next(s for s in week.shifts if s.id == shift_id)


def test_block_shift_makes_the_shift_cant_for_that_employee():
    week = apply_changes(sample_shifts(), sample_employees(), [BlockShift("sam", "fri-dinner-bar")])

    assert employee(week, "sam").ratings["fri-dinner-bar"] == Rating.CANT


def test_changes_only_apply_to_this_week_and_leave_the_originals_alone():
    shifts, employees = sample_shifts(), sample_employees()

    apply_changes(shifts, employees, [BlockShift("sam", "fri-dinner-bar")])

    assert employees[-1].id == "sam"
    assert employees[-1].ratings["fri-dinner-bar"] == Rating.WANT


def test_set_coverage_sets_how_many_people_a_shift_needs_this_week():
    week = apply_changes(sample_shifts(), sample_employees(), [SetCoverage("fri-dinner-server", 4)])

    assert shift(week, "fri-dinner-server").needed == 4


def test_set_coverage_twice_gives_the_same_result_as_once():
    change = SetCoverage("fri-dinner-server", 4)

    week = apply_changes(sample_shifts(), sample_employees(), [change, change])

    assert shift(week, "fri-dinner-server").needed == 4


def test_set_max_shifts_limits_an_employee_this_week():
    week = apply_changes(sample_shifts(), sample_employees(), [SetMaxShifts("taylor", 2)])

    assert employee(week, "taylor").max_shifts_per_week == 2


def test_assign_shift_becomes_a_required_assignment_for_the_solver():
    week = apply_changes(sample_shifts(), sample_employees(), [AssignShift("taylor", "thu-dinner-bar")])

    assert week.required == {("taylor", "thu-dinner-bar")}


def test_unknown_employee_is_rejected_with_its_id():
    with pytest.raises(ValueError, match="morgan"):
        apply_changes(sample_shifts(), sample_employees(), [BlockShift("morgan", "fri-dinner-server")])


def test_unknown_shift_is_rejected_with_its_id():
    with pytest.raises(ValueError, match="fri-brunch-server"):
        apply_changes(sample_shifts(), sample_employees(), [SetCoverage("fri-brunch-server", 2)])


def test_unknown_change_type_is_rejected():
    with pytest.raises(ValueError, match="Unknown change type"):
        apply_changes(sample_shifts(), sample_employees(), ["give Sam Friday off"])
