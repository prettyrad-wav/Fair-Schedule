# Manager commands

The manager types a one-week change in plain English ("give Sam Friday off"). `parse_command` turns it into a list of `Change` objects, `apply_changes` applies them to copies of the week's shifts and employees, and the solver re-solves while keeping as much of the posted schedule as it can. The manager reviews the result before it's posted.

This doc defines the change types and the 12 Test 3 commands with their expected output. Design decisions are at the bottom.

## Change types

All changes apply to one week only. The `Shift` templates and `Employee` records are never edited.

| Type | Fields | Effect before solving | Example |
|---|---|---|---|
| `BlockShift` | `employee_id`, `shift_id` | Employee can't work this shift this week (treated like a Can't rating) | Time off, call-outs |
| `AssignShift` | `employee_id`, `shift_id` | Employee must work this shift this week | "Put Taylor on Thursday bar" |
| `SetCoverage` | `shift_id`, `needed` | Shift needs this many people this week (absolute number, not +1/−1) | Big party, slow night |
| `SetMaxShifts` | `employee_id`, `max_shifts` | Employee's max shifts for this week only | "Taylor only wants 2 shifts" |

Rules for `parse_command`:

- **Days become shifts.** "Friday off" becomes one `BlockShift` for every Friday shift in that employee's roles. Claude gets the shift list, so it can expand days itself.
- **Commands about the posted schedule need the schedule.** "Alex called out Saturday" and "swap Bea's Tuesday" only make sense with the current assignments, so `parse_command` takes the current schedule as input along with shifts and employees.
- **Out-of-scope commands return no changes plus a reason.** Examples are permanent changes (new roles, edits to the standard week), unknown employees, and anything none of the four types can express. The app shows the reason, and the solver doesn't run.

## Test 3 commands

Every command was checked against the sample week (`sample_data.py`, ledger 0, week of 11-09-2026). The changes in the "Expected changes" column all leave a valid schedule.

Baseline schedule they refer to:

| Shift | Assigned |
|---|---|
| mon-dinner-server | Casey, Dana |
| tue-dinner-server | Bea, Eli |
| wed-dinner-server | Bea, Taylor |
| thu-dinner-server | Alex, Casey |
| fri-dinner-server | Alex, Casey, Dana |
| sat-brunch-server | Bea, Eli |
| sat-dinner-server | Alex, Dana, Sam |
| sun-brunch-server | Alex, Bea, Dana |
| sun-dinner-server | Eli, Taylor |
| mon-dinner-bar | Jordan |
| tue-dinner-bar | Sam |
| wed-dinner-bar | Jordan |
| thu-dinner-bar | Riley |
| fri-dinner-bar | Jordan, Riley |
| sat-dinner-bar | Taylor, Jordan |
| sun-brunch-bar | Riley |

Spare capacity: Taylor 1, Riley 1, Sam 2. Everyone else is at their max.

| # | Command | Expected changes | What it tests |
|---|---|---|---|
| 1 | Give Sam Friday off | `BlockShift(sam, fri-dinner-server)`, `BlockShift(sam, fri-dinner-bar)` | Expanding a day across both of Sam's roles. Sam isn't scheduled Friday, so the schedule shouldn't change. |
| 2 | Alex called out Saturday, refill it | `BlockShift(alex, sat-brunch-server)`, `BlockShift(alex, sat-dinner-server)` | Call-out on a posted shift. Blocks the whole day so Alex isn't moved to brunch. The refill has to reshuffle, because every free server is maxed out or already working Saturday. |
| 3 | Riley can't do Sunday brunch this week | `BlockShift(riley, sun-brunch-bar)` | Single-shift block, with the role inferred (Riley only bartends). |
| 4 | Big party Friday, we need one more server | `SetCoverage(fri-dinner-server, 4)` | Relative wording turned into an absolute number (3 → 4). |
| 5 | Monday's dead, only need one server | `SetCoverage(mon-dinner-server, 1)` | Reducing coverage. |
| 6 | Put Taylor on Thursday bar | `AssignShift(taylor, thu-dinner-bar)` | Forcing an assignment. Riley gets bumped. |
| 7 | Taylor only wants 2 shifts this week | `SetMaxShifts(taylor, 2)` | One-week max. |
| 8 | Swap Bea's Tuesday with Dana | `BlockShift(bea, tue-dinner-server)`, `AssignShift(dana, tue-dinner-server)` | Compound command that reads the schedule. Dana is at her max, so one of her other shifts has to move. |
| 9 | Eli's sick Tuesday, and add a second bartender Thursday | `BlockShift(eli, tue-dinner-server)`, `SetCoverage(thu-dinner-bar, 2)` | Two unrelated changes in one command. |
| 10 | Casey can work the bar from now on | No changes. Reason: permanent role change, not a one-week change. | Rejecting a permanent change. |
| 11 | Give Morgan Friday off | No changes. Reason: no employee named Morgan. | Rejecting an unknown employee instead of guessing. |
| 12 | Someone cover Sunday | No changes. Reason: unclear who or which shift. | Asking for clarification instead of guessing. |

## Decisions (11-09-2026)

- **Call-outs are a `BlockShift`, not a separate type.** The solver treats a call-out and time off the same way. A `CallOut` type can be added later if history needs to record call-outs separately.
- **A call-out blocks the employee's whole day.** Someone who called out sick shouldn't be moved to a different shift that day, so #2 blocks both Saturday shifts instead of relying on the keep-the-schedule penalty.
- **`SetCoverage` stores an absolute number.** `needed=4` can be checked and gives the same result if applied twice. Claude works out "one more" from the shift list.
- **Test 3 has 12 commands, 3 of them rejections**: a permanent change, an unknown employee, and an ambiguous command.
