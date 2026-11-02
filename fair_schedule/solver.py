"""
Solver: builds one week's schedule with OR-Tools CP-SAT.

The solver doesn't know where its data comes from. Tests, the simulation, and
the app all load shifts and employees their own way and pass them in.

    solve_week(shifts, employees, ledger, week_start) -> Schedule

Hard rules always hold (coverage, roles, Can't, max shifts, no doubles, no
clopens). Among the schedules that follow them, the solver picks the one with
the lowest fairness-weighted cost (Notes/Fairness-Score.md).
"""

from datetime import date, time

from ortools.sat.python import cp_model

from fair_schedule.models import (
    SHIFT_COST,
    Assignment,
    Employee,
    Rating,
    Schedule,
    Shift,
)

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Fewer hours than this between a closing shift and the next morning's shift
# counts as a clopen. Bar close (11:30pm) to brunch (9:30am) is 10 hours.
MIN_REST_HOURS = 11

# CP-SAT only works with whole numbers, but cost x (1 + ledger) has decimals.
# Multiplying by 100 and rounding keeps two decimal places of precision.
COST_SCALE = 100


def _minutes(t: time) -> int:
    """Minutes since midnight, so times can be subtracted."""
    return t.hour * 60 + t.minute


def _is_clopen(first: Shift, second: Shift) -> bool:
    """True if working `first` and then `second` the next day is too little rest.

    Only looks within one week (Sun -> Mon of the next week isn't checked yet),
    and assumes no shift ends after midnight.
    """
    if DAYS.index(second.day) != DAYS.index(first.day) + 1:
        return False
    rest = (24 * 60 - _minutes(first.end)) + _minutes(second.start)
    return rest < MIN_REST_HOURS * 60


def solve_week(
    shifts: list[Shift],
    employees: list[Employee],
    ledger: dict[str, float],
    week_start: date,
) -> Schedule:
    """Build the schedule for one week.

    `ledger` maps employee id -> their current ledger score. Pass 0 for
    everyone to solve without fairness (the "ledger off" run).

    Raises ValueError if no schedule can follow every hard rule.
    """
    model = cp_model.CpModel()

    # --- 1. Decision variables -------------------------------------------------
    # One yes/no variable per (employee, shift) pair: 1 = works it, 0 = doesn't.
    # 9 employees x 16 shifts = 144 variables.

    works = {}
    for employee in employees:
        for shift in shifts:
            works[employee.id, shift.id] = model.new_bool_var(f"{employee.id}_{shift.id}")

    # --- 2. Constraints (hard rules) --------------------------------------------

    # Coverage: each shift gets exactly the number of people it needs.
    for shift in shifts:
        model.add(sum(works[employee.id, shift.id] for employee in employees) == shift.needed)

    # Roles and availability: nobody works a shift outside their roles, or a
    # shift they rated Can't.
    for employee in employees:
        for shift in shifts:
            if shift.role not in employee.roles or employee.ratings[shift.id] == Rating.CANT:
                model.add(works[employee.id, shift.id] == 0)

    # Max shifts: nobody works more than their weekly max.
    for employee in employees:
        model.add(
            sum(works[employee.id, shift.id] for shift in shifts)
            <= employee.max_shifts_per_week
        )

    # No doubles: nobody works more than one shift on the same day.
    for employee in employees:
        for day in DAYS:
            model.add(sum(works[employee.id, shift.id] for shift in shifts if shift.day == day) <= 1)

    # No clopens: nobody works both shifts in a closing -> opening pair.
    for first in shifts:
        for second in shifts:
            if _is_clopen(first, second):
                for employee in employees:
                    model.add(works[employee.id, first.id] + works[employee.id, second.id] <= 1)

    # --- 3. Objective -------------------------------------------------------------
    # Out of all the schedules that follow the rules, pick the cheapest.
    # Cost of one assignment = SHIFT_COST[rating] x (1 + that employee's ledger).

    # Each term is cost x yes/no variable, so only assigned shifts add to the
    # total. Can't is skipped: it isn't in SHIFT_COST and is never assigned.
    terms = []
    for employee in employees:
        for shift in shifts:
            rating = employee.ratings[shift.id]
            if rating == Rating.CANT:
                continue
            cost = round(SHIFT_COST[rating] * (1 + ledger[employee.id]) * COST_SCALE)
            terms.append(cost * works[employee.id, shift.id])
    model.minimize(sum(terms))

    # --- 4. Solve -----------------------------------------------------------------
    # A fixed seed and a single worker make results repeatable: when two
    # schedules tie on cost, the same one wins every run.

    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 0
    solver.parameters.num_workers = 1
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # CP-SAT doesn't say which rule failed (Spike 1), so for now just say so.
        raise ValueError(f"No valid schedule exists ({solver.status_name(status)}).")

    # --- 5. Build the result -------------------------------------------------------

    assignments = [
        Assignment(employee.id, shift.id)
        for employee in employees
        for shift in shifts
        if solver.boolean_value(works[employee.id, shift.id])
    ]
    return Schedule(week_start, assignments)
