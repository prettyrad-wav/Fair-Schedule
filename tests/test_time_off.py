"""Tests for advance time-off and the weekly change store (decision log, 11-10 and 11-12-2026)."""

from datetime import date

import pytest

from fair_schedule.changes import AssignShift, BlockShift, ChangeStore, SetCoverage, SetMaxShifts, time_off_changes
from fair_schedule.sample_data import sample_employees, sample_shifts

MONDAY = date(2026, 11, 16)
NEXT_MONDAY = date(2026, 11, 23)


def employee(employee_id):
    return next(e for e in sample_employees() if e.id == employee_id)


# --- time_off_changes: "who + which days" -> BlockShifts ------------------------


def test_time_off_blocks_every_shift_that_day_in_the_employees_roles():
    changes = time_off_changes(employee("sam"), ["Fri"], sample_shifts())

    assert changes == [BlockShift("sam", "fri-dinner-server"), BlockShift("sam", "fri-dinner-bar")]


def test_time_off_skips_shifts_outside_the_employees_roles():
    # Bea is a server, so Sunday's bar brunch isn't hers to block.
    changes = time_off_changes(employee("bea"), ["Sun"], sample_shifts())

    assert changes == [BlockShift("bea", "sun-brunch-server"), BlockShift("bea", "sun-dinner-server")]


def test_time_off_covers_several_days():
    changes = time_off_changes(employee("jordan"), ["Sat", "Sun"], sample_shifts())

    assert changes == [BlockShift("jordan", "sat-dinner-bar"), BlockShift("jordan", "sun-brunch-bar")]


def test_time_off_rejects_an_unknown_day():
    with pytest.raises(ValueError, match="Friday"):
        time_off_changes(employee("sam"), ["Friday"], sample_shifts())


# --- ChangeStore: changes kept per week -----------------------------------------


def test_store_returns_the_changes_added_for_a_week():
    store = ChangeStore()
    store.add(MONDAY, [BlockShift("sam", "fri-dinner-bar")])

    assert store.for_week(MONDAY) == [BlockShift("sam", "fri-dinner-bar")]


def test_store_keeps_each_weeks_changes_separate():
    store = ChangeStore()
    store.add(MONDAY, [BlockShift("sam", "fri-dinner-bar")])

    assert store.for_week(NEXT_MONDAY) == []


def test_store_skips_a_change_already_added_that_week():
    store = ChangeStore()
    store.add(MONDAY, [BlockShift("sam", "fri-dinner-bar")])
    store.add(MONDAY, [BlockShift("sam", "fri-dinner-bar"), BlockShift("sam", "fri-dinner-server")])

    assert store.for_week(MONDAY) == [BlockShift("sam", "fri-dinner-bar"), BlockShift("sam", "fri-dinner-server")]


def test_store_removes_one_change():
    store = ChangeStore()
    store.add(MONDAY, [BlockShift("sam", "fri-dinner-bar"), BlockShift("sam", "fri-dinner-server")])

    store.remove(MONDAY, BlockShift("sam", "fri-dinner-bar"))

    assert store.for_week(MONDAY) == [BlockShift("sam", "fri-dinner-server")]


def test_editing_the_returned_list_doesnt_change_the_store():
    store = ChangeStore()
    store.add(MONDAY, [BlockShift("sam", "fri-dinner-bar")])

    store.for_week(MONDAY).clear()

    assert store.for_week(MONDAY) == [BlockShift("sam", "fri-dinner-bar")]


def test_store_rejects_a_week_that_doesnt_start_on_monday():
    with pytest.raises(ValueError, match="Monday"):
        ChangeStore().add(date(2026, 11, 18), [BlockShift("sam", "fri-dinner-bar")])


def test_store_survives_a_round_trip_through_json():
    store = ChangeStore()
    store.add(
        MONDAY,
        [
            BlockShift("sam", "fri-dinner-bar"),
            AssignShift("taylor", "thu-dinner-bar"),
            SetCoverage("fri-dinner-server", 4),
            SetMaxShifts("taylor", 2),
        ],
    )
    store.add(NEXT_MONDAY, [BlockShift("bea", "sun-brunch-server")])

    loaded = ChangeStore.from_json(store.to_json())

    assert loaded.for_week(MONDAY) == store.for_week(MONDAY)
    assert loaded.for_week(NEXT_MONDAY) == store.for_week(NEXT_MONDAY)
