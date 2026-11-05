"""
Explanation facts: everything Claude needs to explain one employee's week.

The code works out the facts and Claude only puts them into words, so an
explanation can never give a reason the data doesn't back up.

    Schedule + LedgerEntry list ──► build_explanation_facts ──► EmployeeFacts list
                                                                    │
                                              (fair_schedule/ai.py) ▼
                                                            plain-English text

No API calls here, so this runs (and can be tested) without a Claude key.
"""

from dataclasses import dataclass, field
from datetime import time

from fair_schedule.models import Employee, LedgerEntry, Rating, Schedule, Shift

# --- 1. Fact types --------------------------------------------------------------


@dataclass
class ShiftFact:
    """One shift from one employee's point of view, plus how in-demand it was.

    The demand numbers are the "why": "Friday close needed 2 bartenders, and
    only 1 of the 4 who could work it wanted it" explains a bad shift better
    than the rating alone.
    """

    shift_id: str
    day: str
    start: str  # "4:00pm", ready to read
    end: str
    role: str
    rating: Rating  # how this employee rated it
    needed: int  # how many people the shift needs
    could_work: int  # people with the right role who didn't rate it Can't
    willing: int  # of those, how many rated it Want or Fine


@dataclass
class EmployeeFacts:
    """Everything about one employee's week that an explanation can mention."""

    employee_id: str
    name: str
    shifts: list[ShiftFact]  # the shifts they got
    # Shifts they rated Want but didn't get, so the explanation can say why.
    missed_wants: list[ShiftFact]
    min_shifts: int
    max_shifts: int
    week_score: float  # average cost of their shifts (0 = all Want)
    ledger_before: float
    ledger_after: float
    # 1 = highest ledger after this week, so first in line next week.
    # People with the same ledger share a rank.
    priority_rank: int
    team_size: int


# --- 2. Helpers -----------------------------------------------------------------


def _clock(t: time) -> str:
    """time(16, 0) -> "4:00pm". Written out because strftime's no-leading-zero
    flag differs between Mac/Linux and Windows."""
    suffix = "am" if t.hour < 12 else "pm"
    return f"{t.hour % 12 or 12}:{t.minute:02d}{suffix}"


def _can_work(employee: Employee, shift: Shift) -> bool:
    """Right role and didn't rate it Can't. Ignores max shifts, doubles, and
    clopens, which depend on the rest of the week."""
    return shift.role in employee.roles and employee.ratings[shift.id] != Rating.CANT


def _shift_fact(shift: Shift, employee: Employee, employees: list[Employee]) -> ShiftFact:
    able = [e for e in employees if _can_work(e, shift)]
    willing = [e for e in able if e.ratings[shift.id] in (Rating.WANT, Rating.FINE)]
    return ShiftFact(
        shift_id=shift.id,
        day=shift.day,
        start=_clock(shift.start),
        end=_clock(shift.end),
        role=shift.role,
        rating=employee.ratings[shift.id],
        needed=shift.needed,
        could_work=len(able),
        willing=len(willing),
    )


# --- 3. Build the facts ---------------------------------------------------------


def build_explanation_facts(
    schedule: Schedule,
    shifts: list[Shift],
    employees: list[Employee],
    ledger_before: dict[str, float],
    entries: list[LedgerEntry],
) -> list[EmployeeFacts]:
    """Work out the facts behind each employee's week.

    `ledger_before` is the dict that was passed to solve_week, and `entries` is
    what update_ledger returned for this schedule. Returns one EmployeeFacts
    per employee, in the same order as `employees`.
    """
    entry_by_id = {entry.employee_id: entry for entry in entries}
    assigned = {(a.employee_id, a.shift_id) for a in schedule.assignments}

    facts = []
    for employee in employees:
        entry = entry_by_id[employee.id]

        got = [s for s in shifts if (employee.id, s.id) in assigned]
        missed = [
            s
            for s in shifts
            if (employee.id, s.id) not in assigned
            and employee.ratings[s.id] == Rating.WANT
            and _can_work(employee, s)
        ]

        # Rank = 1 + how many people ended the week with a higher ledger.
        higher = sum(1 for other in entries if other.ledger > entry.ledger)

        facts.append(
            EmployeeFacts(
                employee_id=employee.id,
                name=employee.name,
                shifts=[_shift_fact(s, employee, employees) for s in got],
                missed_wants=[_shift_fact(s, employee, employees) for s in missed],
                min_shifts=employee.min_shifts_per_week,
                max_shifts=employee.max_shifts_per_week,
                week_score=entry.week_score,
                ledger_before=ledger_before[employee.id],
                ledger_after=entry.ledger,
                priority_rank=higher + 1,
                team_size=len(employees),
            )
        )
    return facts
