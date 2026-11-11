"""
One-week changes from the manager (docs/manager-commands.md).

A manager command ("give Sam Friday off") becomes a list of Change objects.
apply_changes applies them to the week's shifts and employees before the
solver runs.
"""

from copy import deepcopy
from dataclasses import dataclass, field

from fair_schedule.models import Employee, Rating, Shift


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
