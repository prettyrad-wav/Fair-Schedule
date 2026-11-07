"""
Spike 2: does the fairness ledger even out bad shifts over 8 weeks?

Runs the same restaurant for 8 weeks twice:
    - Ledger on: each week's ledger feeds into the next week's solve.
    - Ledger off: the solver gets all zeros every week. update_ledger still
      runs, so we can see what the scores would have been, but they're never
      fed back in.

The solver is deterministic, so with the ledger off it builds the same week
8 times and the same people get the bad shifts every week. If the ledger works,
the ledger-on run spreads total cost more evenly across the staff.

Two numbers judge a run:
    - Spread: max - min of everyone's 8-week total. Lower = fairer over time.
    - Swing: how much a person's week score changes from one week to the next,
      averaged over everyone. Lower = steadier, less "bad week, good week".

Each run is saved to spikes/results/<RUN_NAME>.json so later runs can be
compared against it. Change RUN_NAME before each new experiment.

Run it from the repo root:
    .venv/bin/python -m spikes.8_week_simulation
"""

import json
import statistics
from datetime import date, timedelta
from pathlib import Path

from fair_schedule import fairness, solver
from fair_schedule.fairness import to_scores, update_ledger
from fair_schedule.models import Employee, LedgerEntry, Shift
from fair_schedule.sample_data import sample_employees, sample_shifts
from fair_schedule.solver import solve_week

WEEKS = 8
FIRST_WEEK = date(2026, 11, 2)

# Name of this experiment. The results file is named after it, and an existing
# file is never overwritten, so the baseline can't be lost by accident.
RUN_NAME = "decay0.75_weight3"
RESULTS_DIR = Path(__file__).parent / "results"


def simulate(
    shifts: list[Shift],
    employees: list[Employee],
    ledger_on: bool,
) -> list[list[LedgerEntry]]:
    """Schedule WEEKS weeks in a row. Returns each week's LedgerEntry list."""
    ledger = {employee.id: 0.0 for employee in employees}
    history = []
    for week in range(WEEKS):
        week_start = FIRST_WEEK + timedelta(weeks=week)

        solver_ledger = ledger if ledger_on else {employee.id: 0.0 for employee in employees}
        schedule = solve_week(shifts, employees, solver_ledger, week_start)
        entries = update_ledger(schedule, employees, ledger)
        ledger = to_scores(entries)
        history.append(entries)

    return history


def week_scores(history: list[list[LedgerEntry]]) -> dict[str, list[float]]:
    """Each employee's week score for every week, in order."""
    scores: dict[str, list[float]] = {}
    for entries in history:
        for entry in entries:
            scores.setdefault(entry.employee_id, []).append(entry.week_score)
    return scores


def summarize(history: list[list[LedgerEntry]]) -> dict:
    """The numbers that judge a run: totals, their spread, and the swing."""
    scores = week_scores(history)
    totals = {employee_id: sum(s) for employee_id, s in scores.items()}

    # Swing for one person: average size of the change between back-to-back
    # weeks. 1.50, 0.00, 2.00 has changes of 1.50 and 2.00, so swing 1.75.
    swings = {
        employee_id: statistics.mean(abs(b - a) for a, b in zip(s, s[1:]))
        for employee_id, s in scores.items()
    }

    values = list(totals.values())
    return {
        "totals": totals,
        "swings": swings,
        "spread": max(values) - min(values),
        "std_dev": statistics.pstdev(values),
        "avg_swing": statistics.mean(swings.values()),
    }


def print_run(label: str, history: list[list[LedgerEntry]], employees: list[Employee]) -> None:
    """Print week scores per employee per week, then totals, spread, and swing."""
    print(f"\n=== {label} ===")
    header = "".join(f"{'wk' + str(week + 1):>6}" for week in range(WEEKS))
    print(f"  {'':<7}{header}   total  swing")

    scores = week_scores(history)
    summary = summarize(history)
    for employee in employees:
        row = "".join(f"{score:6.2f}" for score in scores[employee.id])
        print(
            f"  {employee.name:<7}{row}   {summary['totals'][employee.id]:5.2f}"
            f"  {summary['swings'][employee.id]:5.2f}"
        )

    print(
        f"  Spread of totals: max - min = {summary['spread']:.2f}, "
        f"std dev = {summary['std_dev']:.2f}"
    )
    print(f"  Average swing: {summary['avg_swing']:.2f}")


def save_results(runs: dict[str, list[list[LedgerEntry]]]) -> Path:
    """Save the settings, summaries, and every LedgerEntry to RESULTS_DIR/RUN_NAME.json."""
    path = RESULTS_DIR / f"{RUN_NAME}.json"
    if path.exists():
        raise FileExistsError(f"{path} already exists. Change RUN_NAME for a new experiment.")

    data = {
        "run_name": RUN_NAME,
        "settings": {
            "weeks": WEEKS,
            "decay": fairness.DECAY,
            "max_cost_weight": solver.MAX_COST_WEIGHT,
        },
        "runs": {
            label: {
                "summary": summarize(history),
                "entries": [
                    {
                        "week_start": entry.week_start.isoformat(),
                        "employee_id": entry.employee_id,
                        "week_score": entry.week_score,
                        "ledger": entry.ledger,
                    }
                    for entries in history
                    for entry in entries
                ],
            }
            for label, history in runs.items()
        },
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path


shifts = sample_shifts()
employees = sample_employees()

runs = {
    # "ledger_off": simulate(shifts, employees, ledger_on=False),
    "ledger_on": simulate(shifts, employees, ledger_on=True),
}

for label, history in runs.items():
    print_run(label, history, employees)

print(f"\nSaved to {save_results(runs)}")
