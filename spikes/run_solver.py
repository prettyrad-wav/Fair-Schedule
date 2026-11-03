"""
Quick check: run the solver on the sample data and print the week.

Not a test. It just shows the code imports cleanly and the solver finds a
schedule, so you can eyeball the result after a change.

Run it from the repo root:
    .venv/bin/python -m spikes.run_solver

(-m, not spikes/run_solver.py: running a file directly only lets it import
from its own folder, so `import fair_schedule` fails. -m runs it from the
repo root, where fair_schedule lives.)
"""

from datetime import date

from fair_schedule.fairness import update_ledger
from fair_schedule.models import SHIFT_COST
from fair_schedule.sample_data import sample_employees, sample_shifts
from fair_schedule.solver import solve_week

shifts = sample_shifts()
employees = sample_employees()

# Everyone starts at 0, so this is the "ledger off" week.
ledger = {employee.id: 0 for employee in employees}

schedule = solve_week(shifts, employees, ledger, date(2026, 11, 2))
entries = update_ledger(schedule, employees, ledger)

# --- Print the schedule ---------------------------------------------------------

print("Schedule:")
for shift in shifts:
    staff = [a.employee_id for a in schedule.assignments if a.shift_id == shift.id]
    print(f"  {shift.id:<18} {', '.join(staff)}")

print("\nPer employee (shifts, cost, week score, new ledger):")
for employee, entry in zip(employees, entries):
    got = [a.shift_id for a in schedule.assignments if a.employee_id == employee.id]
    cost = sum(SHIFT_COST[employee.ratings[shift_id]] for shift_id in got)
    print(
        f"  {employee.name:<7} {len(got)} shifts, cost {cost}, "
        f"week score {entry.week_score:.2f}, ledger {entry.ledger:.2f}"
    )
