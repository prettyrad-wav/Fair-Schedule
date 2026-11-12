"""
One-week changes from the manager (docs/manager-commands.md).

A time-off request or a manager command ("give Sam Friday off") becomes a list
of Change objects. ChangeStore keeps them per week, and apply_changes applies
a week's changes to the shifts and employees before the solver runs.
"""

import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import date

from fair_schedule.models import Employee, Rating, Shift
from fair_schedule.solver import DAYS


@dataclass(frozen=True)
class BlockShift:
    """The employee can't work this shift this week (time off, call-outs)."""

    employee_id: str
    shift_id: str


@dataclass(frozen=True)
class AssignShift:
    """The employee must work this shift this week."""

    employee_id: str
    shift_id: str


@dataclass(frozen=True)
class SetCoverage:
    """The shift needs this many people this week.

    An absolute number, not +1/-1, so applying it twice gives the same result.
    """

    shift_id: str
    needed: int


@dataclass(frozen=True)
class SetMaxShifts:
    """The employee's max shifts for this week only."""

    employee_id: str
    max_shifts: int


Change = BlockShift | AssignShift | SetCoverage | SetMaxShifts

# Class name -> class, for turning saved JSON back into changes.
CHANGE_TYPES = {cls.__name__: cls for cls in (BlockShift, AssignShift, SetCoverage, SetMaxShifts)}


def time_off_changes(employee: Employee, days: list[str], shifts: list[Shift]) -> list[BlockShift]:
    """Turn an approved time-off request into one BlockShift per shift.

    A day off blocks every shift that day in the employee's roles (decision
    log, 11-09-2026), so they can't be moved to another shift that day. The
    form and any future scheduling-app import both go through this.
    """
    for day in days:
        if day not in DAYS:
            raise ValueError(f"Unknown day: {day!r} (expected one of {', '.join(DAYS)})")
    return [
        BlockShift(employee.id, shift.id)
        for shift in shifts
        if shift.day in days and shift.role in employee.roles
    ]


class ChangeStore:
    """Every week's changes, kept under the Monday that starts the week.

    Weeks, not calendar dates: knowing the week makes a shift id like
    "fri-dinner-server" an exact date (decision log, 11-10-2026).
    """

    def __init__(self) -> None:
        self._weeks: dict[date, list[Change]] = {}

    def add(self, week_start: date, changes: list[Change]) -> None:
        """Add changes to a week, skipping any it already has."""
        if week_start.weekday() != 0:
            raise ValueError(f"A week starts on Monday, not {week_start:%A %Y-%m-%d}")
        week = self._weeks.setdefault(week_start, [])
        for change in changes:
            if change not in week:
                week.append(change)

    def remove(self, week_start: date, change: Change) -> None:
        self._weeks.get(week_start, []).remove(change)

    def for_week(self, week_start: date) -> list[Change]:
        """The week's changes, in the order they were added (a copy)."""
        return list(self._weeks.get(week_start, []))

    def to_json(self) -> str:
        """e.g. {"2026-11-16": [{"type": "BlockShift", "employee_id": "sam", ...}]}"""
        return json.dumps(
            {
                week_start.isoformat(): [{"type": type(c).__name__, **asdict(c)} for c in changes]
                for week_start, changes in sorted(self._weeks.items())
                if changes
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, text: str) -> "ChangeStore":
        store = cls()
        for week_start, changes in json.loads(text).items():
            store.add(
                date.fromisoformat(week_start),
                [CHANGE_TYPES[fields.pop("type")](**fields) for fields in changes],
            )
        return store


@dataclass
class WeekSetup:
    """The week's shifts and employees with the changes applied.

    `required` holds (employee id, shift id) pairs from AssignShift. They can't
    be expressed by editing shifts or employees, so solve_week enforces them.
    """

    shifts: list[Shift]
    employees: list[Employee]
    required: set[tuple[str, str]] = field(default_factory=set)


def apply_changes(shifts: list[Shift], employees: list[Employee], changes: list[Change]) -> WeekSetup:
    """Return copies of the shifts and employees with the changes applied.

    The originals are never edited: they're the standard week, and a change
    only lasts one week.
    """
    shifts = deepcopy(shifts)
    employees = deepcopy(employees)
    employees_by_id = {e.id: e for e in employees}
    shifts_by_id = {s.id: s for s in shifts}

    # Changes come from Claude, so an id may not exist. Fail loudly instead of
    # guessing, and name the id so the manager can see what went wrong.
    def find_employee(employee_id: str) -> Employee:
        if employee_id not in employees_by_id:
            raise ValueError(f"Unknown employee: {employee_id!r}")
        return employees_by_id[employee_id]

    def find_shift(shift_id: str) -> Shift:
        if shift_id not in shifts_by_id:
            raise ValueError(f"Unknown shift: {shift_id!r}")
        return shifts_by_id[shift_id]

    required: set[tuple[str, str]] = set()
    for change in changes:
        match change:
            case BlockShift(employee_id, shift_id):
                find_employee(employee_id).ratings[find_shift(shift_id).id] = Rating.CANT
            case AssignShift(employee_id, shift_id):
                required.add((find_employee(employee_id).id, find_shift(shift_id).id))
            case SetCoverage(shift_id, needed):
                find_shift(shift_id).needed = needed
            case SetMaxShifts(employee_id, max_shifts):
                find_employee(employee_id).max_shifts_per_week = max_shifts
            case _:
                raise ValueError(f"Unknown change type: {change!r}")

    return WeekSetup(shifts, employees, required)
