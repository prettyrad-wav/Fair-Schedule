"""
Fairness ledger: updates each employee's score after a week is scheduled.

The loop each week (Notes/Fairness-Score.md):

    ledger scores ──► solve_week ──► Schedule ──► update_ledger ──► LedgerEntry list
          ▲                                                               │
          └──────────────────────── to_scores ◄───────────────────────────┘

update_ledger makes the LedgerEntry objects that get saved (and charted).
to_scores turns them back into the plain {employee id: ledger} dict that
solve_week reads.
"""

from fair_schedule.models import SHIFT_COST, Employee, LedgerEntry, Schedule

# How much of last week's ledger carries over. 0.5 = old luck halves each week.
DECAY = 0.5


def update_ledger(
    schedule: Schedule,
    employees: list[Employee],
    ledger: dict[str, float],
) -> list[LedgerEntry]:
    """Score everyone's week and work out their new ledger.

    `ledger` is everyone's score going into this week (the same dict that was
    passed to solve_week). Returns one LedgerEntry per employee.
    """
    entries = []
    for employee in employees:
        total_shifts = 0
        total_cost = 0
        for assignment in schedule.assignments: 
            if employee.id == assignment.employee_id:
                total_cost += SHIFT_COST[employee.ratings[assignment.shift_id]] 
                total_shifts += 1
        if total_shifts == 0:
            week_score = 0.0
        else:
            week_score = total_cost / total_shifts
        # TODO (your turn): week score.
        # The average cost of the shifts this employee got this week.
        # Hints:
        #   - Their shifts: assignments in schedule.assignments where
        #     assignment.employee_id == employee.id. Each has a shift_id.
        #   - Cost of one shift: SHIFT_COST[employee.ratings[shift_id]]
        #   - Average = total cost / number of shifts. If they got no shifts,
        #     use 0 (dividing by 0 is an error).
        
         

        new_ledger = DECAY * ledger[employee.id] + week_score

        entries.append(
            LedgerEntry(
                employee_id=employee.id,
                week_start=schedule.week_start,
                week_score=week_score,
                ledger=new_ledger,
            )
        )
    return entries


def to_scores(entries: list[LedgerEntry]) -> dict[str, float]:
    """Turn one week's LedgerEntry list into the dict solve_week takes."""
    return {entry.employee_id: entry.ledger for entry in entries}
