"""
Quick check: run a few weeks on the sample data and print Claude's
explanations for the last one.

Calls the Claude API once (needs ANTHROPIC_API_KEY in .env). Earlier weeks
just build up the ledger, so the explained week has real history behind it.

Run it from the repo root:
    .venv/bin/python -m spikes.explain_week
"""

from datetime import date, timedelta

from fair_schedule.ai import explain_schedule
from fair_schedule.explanations import build_explanation_facts
from fair_schedule.fairness import to_scores, update_ledger
from fair_schedule.sample_data import sample_employees, sample_shifts
from fair_schedule.solver import solve_week

WEEKS = 3

shifts = sample_shifts()
employees = sample_employees()
ledger = {employee.id: 0.0 for employee in employees}

week_start = date(2026, 11, 2)
for week in range(WEEKS):
    schedule = solve_week(shifts, employees, ledger, week_start)
    entries = update_ledger(schedule, employees, ledger)
    if week == WEEKS - 1:
        facts = build_explanation_facts(schedule, shifts, employees, ledger, entries)
    ledger = to_scores(entries)
    week_start += timedelta(weeks=1)

explanations = explain_schedule(facts)

print(f"Week {WEEKS} explanations:\n")
for f in facts:
    shift_list = ", ".join(f"{s.shift_id} ({s.rating})" for s in f.shifts)
    print(f"{f.name} — rank {f.priority_rank}/{f.team_size}: {shift_list}")
    print(f"  {explanations[f.employee_id]}\n")
