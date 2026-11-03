"""
The 8-week simulation chart for the README: Fair-Schedule vs. a "Want first"
scheduler on the same restaurant.

    - Want first: gives everyone as many shifts they want as it can, but has no
      memory. It's the same solver with the ledger and the worst-week term both
      off, so it's the best a manager can do one week at a time. With the same
      ratings every week, it builds the same week 8 times.
    - Fair-Schedule: the real settings (ledger on, worst-week term on).

Both are scored the same way (update_ledger), so the only difference is how
each one picks the schedule.

Run it from the repo root:
    .venv/bin/python -m spikes.simulation_chart
"""

from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to a file, no window
import matplotlib.pyplot as plt

from fair_schedule.fairness import to_scores, update_ledger
from fair_schedule.models import Employee, LedgerEntry, Shift
from fair_schedule.sample_data import sample_employees, sample_shifts
from fair_schedule.solver import solve_week

WEEKS = 8
FIRST_WEEK = date(2026, 11, 2)
CHART_PATH = Path(__file__).parent.parent / "docs" / "images" / "simulation_chart.png"

# Colors and text, checked for colorblind safety (dataviz palette slots 1 and 2).
FAIR_COLOR = "#2a78d6"
WANT_FIRST_COLOR = "#eb6834"
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"


def simulate(
    shifts: list[Shift],
    employees: list[Employee],
    fair: bool,
) -> list[list[LedgerEntry]]:
    """Schedule WEEKS weeks with one scheduler. Returns each week's LedgerEntry list."""
    ledger = {employee.id: 0.0 for employee in employees}
    history = []
    for week in range(WEEKS):
        week_start = FIRST_WEEK + timedelta(weeks=week)
        if fair:
            schedule = solve_week(shifts, employees, ledger, week_start)
        else:
            no_memory = {employee.id: 0.0 for employee in employees}
            schedule = solve_week(shifts, employees, no_memory, week_start, max_cost_weight=0)
        entries = update_ledger(schedule, employees, ledger)
        ledger = to_scores(entries)
        history.append(entries)
    return history


def running_totals(history: list[list[LedgerEntry]]) -> dict[str, list[float]]:
    """Each employee's week scores added up so far, after every week."""
    totals: dict[str, list[float]] = {}
    for entries in history:
        for entry in entries:
            so_far = totals.setdefault(entry.employee_id, [])
            so_far.append((so_far[-1] if so_far else 0.0) + entry.week_score)
    return totals


def gap_by_week(totals: dict[str, list[float]]) -> list[float]:
    """After each week: highest running total minus lowest."""
    return [
        max(t[week] for t in totals.values()) - min(t[week] for t in totals.values())
        for week in range(WEEKS)
    ]


def style(ax) -> None:
    """Recessive axes: no box, light grid, secondary-ink ticks."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, length=0, labelsize=10)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def draw(employees: list[Employee], want_first: dict, fair: dict) -> None:
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(12, 5.4), gridspec_kw={"width_ratios": [1.1, 1]}, facecolor=SURFACE
    )
    names = {employee.id: employee.name for employee in employees}

    # --- Left: each person's 8-week total, Want first vs Fair-Schedule ----------
    order = sorted(names, key=lambda employee_id: want_first[employee_id][-1])
    for row, employee_id in enumerate(order):
        a, b = want_first[employee_id][-1], fair[employee_id][-1]
        left.plot([a, b], [row, row], color=GRID, linewidth=2, zorder=1)
    left.scatter(
        [want_first[i][-1] for i in order], range(len(order)), s=70, color=WANT_FIRST_COLOR,
        edgecolor=SURFACE, linewidth=2, zorder=2, label="Want first (no memory)",
    )
    left.scatter(
        [fair[i][-1] for i in order], range(len(order)), s=70, color=FAIR_COLOR,
        edgecolor=SURFACE, linewidth=2, zorder=3, label="Fair-Schedule",
    )
    left.set_yticks(range(len(order)), [names[i] for i in order])
    left.set_xlim(0, None)
    left.set_xlabel("Total bad-shift score after 8 weeks", color=TEXT_SECONDARY)
    left.set_title("Who carries the bad shifts", loc="left", color=TEXT_PRIMARY, fontsize=12)
    style(left)
    left.grid(axis="y", visible=False)

    # --- Right: gap between the most and least burdened person, week by week ---
    weeks = range(1, WEEKS + 1)
    for gaps, color, label in (
        (gap_by_week(want_first), WANT_FIRST_COLOR, "Want first"),
        (gap_by_week(fair), FAIR_COLOR, "Fair-Schedule"),
    ):
        right.plot(weeks, gaps, color=color, linewidth=2, marker="o", markersize=7,
                   markeredgecolor=SURFACE, markeredgewidth=2)
        right.annotate(f"{label}  {gaps[-1]:.1f}", (WEEKS, gaps[-1]), xytext=(8, 0),
                       textcoords="offset points", va="center", color=TEXT_PRIMARY, fontsize=10)
    right.set_xticks(list(weeks))
    right.set_xlim(0.7, WEEKS + 2.2)
    right.set_ylim(0, None)
    right.set_xlabel("Week", color=TEXT_SECONDARY)
    right.set_title("Gap between most and least burdened", loc="left", color=TEXT_PRIMARY,
                    fontsize=12)
    style(right)
    right.grid(axis="x", visible=False)

    fig.suptitle(
        "Same restaurant, 8 weeks: Fair-Schedule spreads the bad shifts out",
        x=0.01, ha="left", fontsize=14, color=TEXT_PRIMARY, fontweight="bold",
    )
    fig.text(
        0.01, 0.905,
        "Bad-shift score per week = average cost of the shifts someone got "
        "(Want 0, Fine 1, Prefer not 3). Lower is better.",
        ha="left", fontsize=10, color=TEXT_SECONDARY,
    )
    fig.legend(
        handles=left.collections, loc="upper left", bbox_to_anchor=(0.005, 0.89), ncol=2,
        frameon=False, fontsize=10, labelcolor=TEXT_PRIMARY,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.83))

    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, dpi=160, facecolor=SURFACE)


shifts = sample_shifts()
employees = sample_employees()

want_first = running_totals(simulate(shifts, employees, fair=False))
fair = running_totals(simulate(shifts, employees, fair=True))
draw(employees, want_first, fair)

for label, totals in (("Want first", want_first), ("Fair-Schedule", fair)):
    print(f"{label:<14} gap after {WEEKS} weeks: {gap_by_week(totals)[-1]:.2f}")
print(f"Saved to {CHART_PATH}")
