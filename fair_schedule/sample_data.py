"""
Sample data: a fake restaurant for tests, the 8-week simulation, and the demo.

The data is built so fairness actually matters:
    - A few shifts almost everyone rates Prefer not (Monday dinner, Sunday
      brunch after a Saturday close). Without the ledger, the solver sees a tie
      between staff on those shifts and can hand them to the same people every
      week.
    - Coverage is tight: 30 slots to fill and 34 shifts of total capacity, so
      bad shifts can't all go to whoever has spare room.
    - Two people work both roles, so the solver has some choices to make.

Everything is written by hand (no randomness), so every run sees the same week.
"""

from datetime import time

from fair_schedule.models import Employee, Rating, Shift

# --- 1. Shifts ----------------------------------------------------------------
# Servers work dinner Mon-Sun plus weekend brunch. The bar works dinner to close
# Mon-Sat plus Sunday brunch. Bar close is 11:30pm and brunch starts at 9:30am,
# so closing Saturday and opening Sunday is a clopen.

BRUNCH = (time(9, 30), time(15, 0))
SERVER_DINNER = (time(16, 30), time(22, 30))
BAR_DINNER = (time(16, 0), time(23, 30))


def sample_shifts() -> list[Shift]:
    """The restaurant's weekly shifts: 16 shifts, 30 people needed in total."""
    return [
        # Servers: 9 shifts, 21 people
        Shift("mon-dinner-server", "Mon", *SERVER_DINNER, "server", 2),
        Shift("tue-dinner-server", "Tue", *SERVER_DINNER, "server", 2),
        Shift("wed-dinner-server", "Wed", *SERVER_DINNER, "server", 2),
        Shift("thu-dinner-server", "Thu", *SERVER_DINNER, "server", 2),
        Shift("fri-dinner-server", "Fri", *SERVER_DINNER, "server", 3),
        Shift("sat-brunch-server", "Sat", *BRUNCH, "server", 2),
        Shift("sat-dinner-server", "Sat", *SERVER_DINNER, "server", 3),
        Shift("sun-brunch-server", "Sun", *BRUNCH, "server", 3),
        Shift("sun-dinner-server", "Sun", *SERVER_DINNER, "server", 2),
        # Bar: 7 shifts, 9 people
        Shift("mon-dinner-bar", "Mon", *BAR_DINNER, "bartender", 1),
        Shift("tue-dinner-bar", "Tue", *BAR_DINNER, "bartender", 1),
        Shift("wed-dinner-bar", "Wed", *BAR_DINNER, "bartender", 1),
        Shift("thu-dinner-bar", "Thu", *BAR_DINNER, "bartender", 1),
        Shift("fri-dinner-bar", "Fri", *BAR_DINNER, "bartender", 2),
        Shift("sat-dinner-bar", "Sat", *BAR_DINNER, "bartender", 2),
        Shift("sun-brunch-bar", "Sun", *BRUNCH, "bartender", 1),
    ]


# --- 2. Ratings ---------------------------------------------------------------
# How most of the staff rates each shift. Each employee starts from these and
# changes a few (section 3). Starting everyone from the same ratings is what
# creates the ties the fairness ledger has to break.
#   Want: Fri/Sat dinner (busy, best tips)
#   Prefer not: slow nights (Mon, Tue bar, Sun dinner) and Sunday brunch

COMMON_RATINGS: dict[str, Rating] = {
    "mon-dinner-server": Rating.PREFER_NOT,
    "tue-dinner-server": Rating.FINE,
    "wed-dinner-server": Rating.FINE,
    "thu-dinner-server": Rating.FINE,
    "fri-dinner-server": Rating.WANT,
    "sat-brunch-server": Rating.FINE,
    "sat-dinner-server": Rating.WANT,
    "sun-brunch-server": Rating.PREFER_NOT,
    "sun-dinner-server": Rating.PREFER_NOT,
    "mon-dinner-bar": Rating.PREFER_NOT,
    "tue-dinner-bar": Rating.PREFER_NOT,
    "wed-dinner-bar": Rating.FINE,
    "thu-dinner-bar": Rating.FINE,
    "fri-dinner-bar": Rating.WANT,
    "sat-dinner-bar": Rating.WANT,
    "sun-brunch-bar": Rating.PREFER_NOT,
}

# --- 3. Employees -------------------------------------------------------------
# 9 fake employees: 5 servers, 2 bartenders, and 2 who work both roles.
# Each one is (id, name, roles, max shifts per week, ratings that differ from
# COMMON_RATINGS).

STAFF = [
    ("alex", "Alex", ["server"], 4, {
        # Evening classes
        "tue-dinner-server": Rating.CANT,
        "wed-dinner-server": Rating.CANT,
    }),
    ("bea", "Bea", ["server"], 4, {
        # Morning person with a second job on Fridays
        "sun-brunch-server": Rating.WANT,
        "fri-dinner-server": Rating.CANT,
    }),
    ("casey", "Casey", ["server"], 3, {
        # No weekend mornings
        "sat-brunch-server": Rating.CANT,
        "sun-brunch-server": Rating.CANT,
    }),
    ("dana", "Dana", ["server"], 4, {
        # Doesn't mind slow Mondays
        "mon-dinner-server": Rating.FINE,
    }),
    ("eli", "Eli", ["server"], 3, {
        "thu-dinner-server": Rating.CANT,
        "sun-dinner-server": Rating.FINE,
    }),
    ("taylor", "Taylor", ["server", "bartender"], 4, {
        "mon-dinner-server": Rating.CANT,
        "mon-dinner-bar": Rating.CANT,
    }),
    ("jordan", "Jordan", ["bartender"], 4, {
        "sun-brunch-bar": Rating.CANT,
    }),
    ("riley", "Riley", ["bartender"], 4, {
        "wed-dinner-bar": Rating.CANT,
    }),
    # Rates everything like everyone else
    ("sam", "Sam", ["bartender", "server"], 4, {}),
]


def sample_employees() -> list[Employee]:
    """The 9 sample employees, each with a rating for every shift.

    Ratings for shifts outside someone's roles are filled in too (the form
    rates every shift), but the solver ignores them.
    """
    return [
        Employee(
            id=employee_id,
            name=name,
            roles=roles,
            max_shifts_per_week=max_shifts,
            ratings={**COMMON_RATINGS, **changes},
        )
        for employee_id, name, roles, max_shifts, changes in STAFF
    ]
