"""
Data model: the things Fair-Schedule stores and how they connect.

These classes don't know about storage. The solver takes them as input, and a
separate save/load layer will turn them into JSON (or SQLite) later.

    Employee --rates--> Shift          (one rating per employee per shift)
    Schedule --has many--> Assignment  (one employee working one shift)
    LedgerEntry                        (one per employee per week)
"""

from dataclasses import dataclass, field
from datetime import date, time
from enum import StrEnum

# --- 1. Ratings ---------------------------------------------------------------
# The four answers on the preference form. StrEnum means each value is also a
# plain string ("want"), so it saves to JSON as-is.


class Rating(StrEnum):
    WANT = "want"
    FINE = "fine"
    PREFER_NOT = "prefer_not"
    CANT = "cant"


# Fairness cost of getting a shift with each rating (Notes/Fairness-Score.md).
# Can't has no cost because it's a hard rule: the solver never assigns it.
SHIFT_COST: dict[Rating, int] = {
    Rating.WANT: 0,
    Rating.FINE: 1,
    Rating.PREFER_NOT: 3
}


# --- 2. Setup: what the manager and employees enter ---------------------------


@dataclass
class Shift:
    """A weekly shift template, like "every Friday, bar, 5pm to close"."""

    id: str  # e.g. "fri-dinner-bar"
    day: str  # "Mon" to "Sun"
    start: time
    end: time
    role: str  # e.g. "server", "bartender", "cook"
    needed: int  # how many people this shift needs


@dataclass
class Employee:
    """One staff member and their answers on the preference form."""

    id: str
    name: str
    roles: list[str]  # roles they can work; they're only scheduled for these
    max_shifts_per_week: int
    # Shift id -> rating. The form rates every shift, so every shift has one.
    ratings: dict[str, Rating] = field(default_factory=dict)


# --- 3. Results: what the app produces each week ------------------------------


@dataclass
class Assignment:
    """One employee working one shift."""

    employee_id: str
    shift_id: str


@dataclass
class Schedule:
    """The solver's output for one week."""

    week_start: date  # the Monday of that week
    assignments: list[Assignment] = field(default_factory=list)


@dataclass
class LedgerEntry:
    """One employee's fairness numbers after one week.

    Stored every week (not just the latest), so the 8-week simulation chart
    can plot how the ledger changes.
    """

    employee_id: str
    week_start: date
    week_score: float  # average cost of the shifts they got that week
    ledger: float  # 0.5 * previous ledger + week_score
