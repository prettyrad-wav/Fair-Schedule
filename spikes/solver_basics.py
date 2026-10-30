"""
Spike 1: OR-Tools CP-SAT basics.

Question: can I get a valid schedule and understand the solver basics?
Setup: 5 employees, 10 shifts, and the hard rules (coverage, availability).

Run it from the repo root:
    .venv/bin/python spikes/solver_basics.py
"""

from ortools.sat.python import cp_model

# --- 1. Data ------------------------------------------------------------------
# Fake employees and a simple week: a lunch and a dinner shift, Monday to Friday.

EMPLOYEES = ["Alex", "Bea", "Carlos", "Dana", "Eli"]

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
# Vault notes: Notes/Python-List-Comprehensions.md, Notes/Python-Tuples.md
SHIFTS = [(day, period) for day in DAYS for period in ["lunch", "dinner"]]

# How many people each shift needs.
NEEDED = {"lunch": 2, "dinner": 3}

# Shifts each employee can't work. Anything not listed counts as available.
UNAVAILABLE = {
    "Alex": [("Mon", "lunch"), ("Tue", "lunch")],
    "Bea": [("Wed", "dinner"), ("Thu", "dinner")],
    "Carlos": [("Fri", "lunch"), ("Fri", "dinner")],
    "Dana": [("Mon", "dinner")],
    "Eli": [("Tue", "lunch"), ("Thu", "lunch")],
}

model = cp_model.CpModel()

# --- 2. Decision variables ----------------------------------------------------
# One yes/no variable for every (employee, shift) pair: 1 = works it, 0 = doesn't.
# 5 employees x 10 shifts = 50 variables. The solver's job is to pick a value
# for each one so that every rule below holds.
# Vault note: Notes/CP-SAT-Decision-Variable-Syntax.md

works = {}
for employee in EMPLOYEES:
    for day, period in SHIFTS:
        works[employee, (day, period)] = model.new_bool_var(f"{employee}_{day}_{period}")

# --- 3. Constraints (hard rules) ----------------------------------------------
# These aren't instructions that run in order. Each one is a fact the final
# answer must satisfy, and the solver searches for values that satisfy all of them.

# Coverage: each shift gets exactly the number of people it needs.
for day, period in SHIFTS:
    model.add(sum(works[employee, (day, period)] for employee in EMPLOYEES) == NEEDED[period])

# Availability: nobody is scheduled for a shift they can't work.
for employee, shifts in UNAVAILABLE.items():
    for shift in shifts:
        model.add(works[employee, shift] == 0)

# TODO (your turn): max shifts per week.
# Right now nothing stops the solver from giving one person most of the shifts.
# Add a constraint so no employee works more than MAX_SHIFTS_PER_WEEK shifts.
# Hint: it looks a lot like the coverage rule, but it loops over employees
# and sums across shifts instead.
MAX_SHIFTS_PER_WEEK = 4
for employee in EMPLOYEES:
    model.add(sum(works[employee, (day,period)] for day, period in SHIFTS) <= MAX_SHIFTS_PER_WEEK)
# --- 4. Solve -----------------------------------------------------------------

solver = cp_model.CpSolver()
status = solver.solve(model)

if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    print(f"No valid schedule exists ({solver.status_name(status)}).")
    raise SystemExit(1)

# --- 5. Print the schedule ----------------------------------------------------

print("Schedule:")
for day, period in SHIFTS:
    staff = [e for e in EMPLOYEES if solver.boolean_value(works[e, (day, period)])]
    print(f"  {day} {period:<6}  {', '.join(staff)}")

print("\nShifts per employee:")
for employee in EMPLOYEES:
    count = sum(solver.boolean_value(works[employee, shift]) for shift in SHIFTS)
    print(f"  {employee:<7} {count}")
