"""
Fair-Schedule web app (Streamlit).

A thin layer over the fair_schedule package: every button calls the same
functions the spikes use. Nothing is saved to disk. The app's state (weeks
generated so far, the ledger, explanations) lives in st.session_state, so it
resets when the page reloads (decision log, 11-04-2026).

Run it from the repo root:
    .venv/bin/streamlit run app.py
"""

from dataclasses import dataclass, field
from datetime import date, time, timedelta

import anthropic
import pandas as pd
import streamlit as st

from fair_schedule.ai import explain_schedule
from fair_schedule.changes import BlockShift, ChangeStore, apply_changes, time_off_changes
from fair_schedule.explanations import EmployeeFacts, build_explanation_facts
from fair_schedule.fairness import to_scores, update_ledger
from fair_schedule.models import Employee, LedgerEntry, Rating, Schedule, Shift
from fair_schedule.sample_data import sample_employees, sample_shifts
from fair_schedule.solver import DAYS, MIN_REST_HOURS, solve_week

st.set_page_config(page_title="Fair-Schedule", page_icon="🗓️", layout="wide")

RATING_LABELS = {
    Rating.WANT: "Want",
    Rating.FINE: "Fine",
    Rating.PREFER_NOT: "Prefer not",
    Rating.CANT: "Can't",
}


# --- 1. State -------------------------------------------------------------------


@dataclass
class Week:
    """Everything the app keeps about one generated week."""

    number: int  # 1, 2, 3... in the order they were generated
    schedule: Schedule
    entries: list[LedgerEntry]  # everyone's ledger after this week
    facts: list[EmployeeFacts]  # worked out when the week is generated (no API)
    min_rest_hours: float
    explanations: dict[str, str] | None = None  # filled in when Claude is called


@dataclass
class AppState:
    shifts: list[Shift]
    employees: list[Employee]
    ledger: dict[str, float]  # everyone's ledger going into the next week
    first_monday: date
    weeks: list[Week] = field(default_factory=list)
    changes: ChangeStore = field(default_factory=ChangeStore)  # time off, per week


def _this_monday() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


def _new_state() -> AppState:
    employees = sample_employees()
    return AppState(
        shifts=sample_shifts(),
        employees=employees,
        ledger={employee.id: 0.0 for employee in employees},
        first_monday=_this_monday(),
    )


if "app" not in st.session_state:
    st.session_state.app = _new_state()
app: AppState = st.session_state.app

names = {employee.id: employee.name for employee in app.employees}


# --- 2. Helpers -----------------------------------------------------------------


def _clock(t: time) -> str:
    """time(16, 30) -> "4:30pm"."""
    hour = t.hour % 12 or 12
    suffix = "am" if t.hour < 12 else "pm"
    return f"{hour}:{t.minute:02d}{suffix}"


def _shift_label(shift: Shift) -> str:
    """e.g. "Fri dinner, bartender (4:00pm–11:30pm)"."""
    meal = "brunch" if shift.start.hour < 12 else "dinner"
    return f"{shift.day} {meal}, {shift.role} ({_clock(shift.start)}–{_clock(shift.end)})"


def _week_start(number: int) -> date:
    """The Monday of week 1, 2, 3..."""
    return app.first_monday + timedelta(weeks=number - 1)


def generate_week() -> None:
    """Solve the next week, update the ledger, and add it to the history."""
    week_start = _week_start(len(app.weeks) + 1)
    rest_hours = st.session_state.min_rest_hours
    # This week's time off is applied to copies; the standard week never changes.
    setup = apply_changes(app.shifts, app.employees, app.changes.for_week(week_start))
    try:
        schedule = solve_week(
            setup.shifts,
            setup.employees,
            app.ledger,
            week_start,
            min_rest_hours=rest_hours,
            required=setup.required,
        )
    except ValueError as error:
        st.session_state.solve_error = str(error)
        return

    entries = update_ledger(schedule, setup.employees, app.ledger)
    facts = build_explanation_facts(schedule, setup.shifts, setup.employees, app.ledger, entries)
    app.weeks.append(Week(len(app.weeks) + 1, schedule, entries, facts, rest_hours))
    app.ledger = to_scores(entries)
    st.session_state.solve_error = None
    st.session_state.selected_week = len(app.weeks)  # jump to the new week


def schedule_grid(week: Week) -> pd.DataFrame:
    """Days across the top, shift types down the side, names in the cells."""
    by_shift: dict[str, list[str]] = {shift.id: [] for shift in app.shifts}
    for assignment in week.schedule.assignments:
        by_shift[assignment.shift_id].append(names[assignment.employee_id])

    rows: dict[str, dict[str, str]] = {}
    for shift in app.shifts:
        meal = "Brunch" if shift.start.hour < 12 else "Dinner"
        row = f"{meal} · {shift.role}"
        cell = ", ".join(sorted(by_shift[shift.id]))
        rows.setdefault(row, {})[shift.day] = f"{cell}  ({len(by_shift[shift.id])}/{shift.needed})"

    order = ["Brunch · server", "Brunch · bartender", "Dinner · server", "Dinner · bartender"]
    frame = pd.DataFrame.from_dict(rows, orient="index").reindex(columns=DAYS)
    frame = frame.reindex([r for r in order if r in rows] + [r for r in rows if r not in order])
    return frame.fillna("—")


# --- 3. Sidebar -------------------------------------------------------------------

with st.sidebar:
    st.header("Settings")
    st.number_input(
        "Minimum rest between shifts (hours)",
        min_value=6.0,
        max_value=14.0,
        value=float(MIN_REST_HOURS),
        step=0.5,
        key="min_rest_hours",
        help="Closing one night and opening the next morning with less rest "
        "than this is a clopen, and the solver never schedules one. Applies "
        "to weeks generated after you change it.",
    )

    if app.weeks:
        st.selectbox(
            "Week to view",
            options=[week.number for week in app.weeks],
            format_func=lambda n: f"Week {n} ({_week_start(n):%b %d})",
            key="selected_week",
        )

    st.divider()
    if st.button("Start over", help="Clear every week and reset the ledger to 0."):
        st.session_state.app = _new_state()
        st.session_state.pop("selected_week", None)
        st.rerun()

    st.caption(
        "Demo data: a fake restaurant with 9 staff and 16 weekly shifts. "
        "Nothing is saved; reloading the page starts over."
    )


# --- 4. Page ----------------------------------------------------------------------

st.title("Fair-Schedule")
st.write(
    "Builds a restaurant's weekly schedule that meets every hard rule, then "
    "balances bad shifts fairly over time. Each week, people who got stuck with "
    "shifts they didn't want move up in line for the next one."
)

week: Week | None = None
if app.weeks:
    week = app.weeks[st.session_state.get("selected_week", len(app.weeks)) - 1]

schedule_tab, time_off_tab, explain_tab, fairness_tab, staff_tab = st.tabs(
    ["Schedule", "Time off", "Explanations", "Fairness over time", "Staff & shifts"]
)

# --- 4a. Schedule ---

with schedule_tab:
    next_number = len(app.weeks) + 1
    st.button(
        f"Generate week {next_number}",
        type="primary",
        on_click=generate_week,
    )
    if blocked := app.changes.for_week(_week_start(next_number)):
        st.caption(f"Week {next_number} has time off approved ({len(blocked)} shifts blocked). See the Time off tab.")
    if st.session_state.get("solve_error"):
        st.error(st.session_state.solve_error)

    if week is None:
        st.info("Generate a week to see the schedule. Generate a few to watch the fairness ledger work.")
    else:
        week_start = week.schedule.week_start
        st.subheader(f"Week {week.number}: {week_start:%b %d} – {week_start + timedelta(days=6):%b %d}")
        st.caption(
            "Names on each shift, with (people scheduled / people needed). "
            f"Minimum rest between shifts: {week.min_rest_hours:g} hours."
        )
        st.dataframe(schedule_grid(week), width="stretch")

        st.subheader("How everyone's week went")
        st.caption(
            "Week score = average cost of their shifts (Want 0, Fine 1, Prefer not 3). "
            "Ledger = 0.75 × last week's ledger + this week's score. "
            "The highest ledger goes first in line next week."
        )
        facts_by_id = {f.employee_id: f for f in week.facts}
        summary = pd.DataFrame(
            [
                {
                    "Employee": names[entry.employee_id],
                    "Shifts": len(facts_by_id[entry.employee_id].shifts),
                    "Prefer-not shifts": sum(
                        s.rating == Rating.PREFER_NOT for s in facts_by_id[entry.employee_id].shifts
                    ),
                    "Week score": round(entry.week_score, 2),
                    "Ledger": round(entry.ledger, 2),
                    "Priority next week": facts_by_id[entry.employee_id].priority_rank,
                }
                for entry in week.entries
            ]
        ).sort_values("Priority next week")
        st.dataframe(summary, hide_index=True, width="stretch")

# --- 4b. Time off ---

with time_off_tab:
    st.write(
        "Enter time off you've already approved. A day off blocks every shift that "
        "day in the employee's roles, and the solver works around it when you "
        "generate that week. Weeks already generated can't change here."
    )
    upcoming = [len(app.weeks) + n for n in range(1, 5)]  # the next 4 weeks to generate

    with st.form("time_off", clear_on_submit=True):
        number = st.selectbox(
            "Week", upcoming, format_func=lambda n: f"Week {n} ({_week_start(n):%b %d})"
        )
        employee_id = st.selectbox("Employee", list(names), format_func=names.get)
        days = st.multiselect("Days off", DAYS)
        if st.form_submit_button("Add time off", type="primary"):
            if not days:
                st.warning("Pick at least one day.")
            else:
                employee = next(e for e in app.employees if e.id == employee_id)
                app.changes.add(_week_start(number), time_off_changes(employee, days, app.shifts))
                st.rerun()  # so the Schedule tab, drawn above, sees the new time off

    shifts_by_id = {shift.id: shift for shift in app.shifts}
    has_any = False
    for number in upcoming:
        week_start = _week_start(number)
        changes = app.changes.for_week(week_start)
        if not changes:
            continue
        has_any = True
        st.subheader(f"Week {number} ({week_start:%b %d})")
        for i, change in enumerate(changes):
            left, right = st.columns([5, 1])
            if isinstance(change, BlockShift):
                left.write(f"{names[change.employee_id]}: off {_shift_label(shifts_by_id[change.shift_id])}")
            else:
                left.write(str(change))
            if right.button("Remove", key=f"remove-{number}-{i}"):
                app.changes.remove(week_start, change)
                st.rerun()
    if not has_any:
        st.info("No time off entered for the next 4 weeks.")

# --- 4c. Explanations ---

with explain_tab:
    if week is None:
        st.info("Generate a week first.")
    else:
        st.write(
            "Claude writes each employee a short note about their week. It only "
            "gets facts the app worked out (their shifts, how in-demand each one "
            "was, why they missed shifts they wanted), so it can't make up a reason. "
            "It never changes the schedule."
        )
        if week.explanations is None:
            if st.button(f"Write explanations for week {week.number}", type="primary"):
                with st.spinner("Claude is writing the explanations..."):
                    try:
                        week.explanations = explain_schedule(week.facts)
                    except (anthropic.AnthropicError, RuntimeError) as error:
                        st.error(
                            "Couldn't get explanations from Claude right now "
                            "(the demo's API credit may have run out). "
                            f"Details: {error}"
                        )
                if week.explanations is not None:
                    st.rerun()

        if week.explanations is not None:
            shifts_by_id = {shift.id: shift for shift in app.shifts}
            for f in sorted(week.facts, key=lambda f: f.name):
                with st.container(border=True):
                    st.markdown(f"**{f.name}**")
                    shift_list = ", ".join(
                        f"{_shift_label(shifts_by_id[s.shift_id])}: {RATING_LABELS[s.rating]}"
                        for s in f.shifts
                    )
                    st.caption(shift_list or "No shifts this week")
                    st.write(week.explanations[f.employee_id])

# --- 4d. Fairness over time ---

with fairness_tab:
    if week is None:
        st.info("Generate a few weeks to see the ledger change.")
    else:
        st.subheader("Ledger by week")
        st.caption(
            "Higher = had a rougher run lately, so gets priority next. "
            "Lines that stay close together mean the bad shifts are being shared."
        )
        ledger_frame = pd.DataFrame(
            {
                w.number: {names[e.employee_id]: e.ledger for e in w.entries}
                for w in app.weeks
            }
        ).T
        ledger_frame.index.name = "Week"
        st.line_chart(ledger_frame)

    st.subheader("8-week simulation")
    st.write(
        "The same restaurant over 8 weeks, compared with a \"Want first\" scheduler "
        "that gives everyone as many Want shifts as it can each week but has no "
        "memory. After 8 weeks the gap between the most and least burdened person "
        "is 13.33 for Want first and 1.50 for Fair-Schedule."
    )
    st.image("docs/images/simulation_chart.png")

# --- 4e. Staff & shifts ---

with staff_tab:
    st.subheader("Staff")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Name": employee.name,
                    "Roles": ", ".join(employee.roles),
                    "Min shifts / week": employee.min_shifts_per_week,
                    "Max shifts / week": employee.max_shifts_per_week,
                }
                for employee in app.employees
            ]
        ),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Preference form answers")
    st.caption("How each person rated each shift. — means the shift isn't in their roles.")
    ratings = pd.DataFrame(
        {
            employee.name: {
                _shift_label(shift): (
                    RATING_LABELS[employee.ratings[shift.id]]
                    if shift.role in employee.roles
                    else "—"
                )
                for shift in app.shifts
            }
            for employee in app.employees
        }
    )
    st.dataframe(ratings, width="stretch", height=600)

    st.subheader("Weekly shifts")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Shift": _shift_label(shift),
                    "Role": shift.role,
                    "People needed": shift.needed,
                }
                for shift in app.shifts
            ]
        ),
        hide_index=True,
        width="stretch",
    )
