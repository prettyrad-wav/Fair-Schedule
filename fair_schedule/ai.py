"""
Claude features: the only module that calls the Claude API.

    explain_schedule(facts) -> {employee id: explanation}

Claude never sees the solver or changes the schedule. It gets the facts
worked out in fair_schedule/explanations.py and writes them up in plain
English.

The API key comes from ANTHROPIC_API_KEY: a .env file locally (see
.env.example), Streamlit secrets once deployed.
"""

import json
from dataclasses import asdict

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from fair_schedule.explanations import EmployeeFacts

MODEL = "claude-opus-5-5"

# If Claude's safety filters decline a request, the API retries it on a
# fallback model it picks, instead of failing.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


def _client() -> anthropic.Anthropic:
    load_dotenv()  # no-op if there's no .env file, so it's safe when deployed
    return anthropic.Anthropic()


# --- 1. Explanations ------------------------------------------------------------

EXPLAIN_SYSTEM = """\
You write short notes explaining a restaurant's weekly schedule to each \
employee. The schedule was built by a solver that balances staff preferences \
fairly over time. You don't change it; you explain it.

You get one JSON object per employee:
- shifts: the shifts they got. rating is how they rated it on the preference \
form (want, fine, prefer_not). needed / could_work / willing / wanted describe \
demand for that shift across the whole team: how many people it needed, how \
many had the right role and didn't rate it Can't, how many of those rated it \
Want or Fine, and how many rated it Want.
- missed_wants: shifts they rated Want but didn't get, with the same numbers \
plus why_missed, the reason they didn't get it:
  - already_working_that_day: they already have a shift that day (nobody \
works two shifts in one day).
  - would_be_clopen: it would leave too little rest next to a shift they got.
  - at_max_shifts: they already have their max shifts for the week.
  - given_to_others: no rule blocked it; the spots went to other people this \
week.
- week_score: average cost of their shifts this week (Want 0, Fine 1, Prefer \
not 3). Higher means a worse week.
- ledger_before / ledger_after: their fairness score going into and coming \
out of this week. A higher score means higher priority next week. Old weeks \
fade, so one bad week doesn't count forever.
- priority_rank (1 = first in line next week) out of team_size.

For each employee, write 2 to 4 sentences, speaking to them directly ("you"):
- Name their shifts in plain words (e.g. "Sunday bar brunch"), not ids.
- If they got a prefer_not shift, say why using the demand numbers (e.g. "it \
needed 1 bartender and none of the 3 who could work it wanted it").
- If they missed shifts they wanted, say so briefly and give the why_missed \
reason. Use "wanted" (not "willing") when saying how many people wanted it.
- Say how this week affects next week. If their rank is near the top, tell \
them they'll get priority.
- Only use the facts given. Never guess at other reasons, never name or \
compare other employees, and don't quote raw scores (describe them instead).
- Friendly and plain, like a fair manager. No greetings or sign-offs.
"""


class _Explanation(BaseModel):
    employee_id: str
    explanation: str


class _Explanations(BaseModel):
    explanations: list[_Explanation]


def explain_schedule(facts: list[EmployeeFacts]) -> dict[str, str]:
    """Write a plain-English explanation of the week for each employee.

    One API call for the whole team. Raises RuntimeError if Claude declines,
    or if the reply skips anyone.
    """
    payload = json.dumps([asdict(f) for f in facts], indent=2, default=str)

    response = _client().beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "medium"},
        betas=[FALLBACK_BETA],
        fallbacks="default",
        system=EXPLAIN_SYSTEM,
        messages=[{"role": "user", "content": f"This week's facts:\n\n{payload}"}],
        output_format=_Explanations,
    )

    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to write the explanations.")
    if response.parsed_output is None:
        raise RuntimeError(f"No explanations returned (stop reason: {response.stop_reason}).")

    explanations = {e.employee_id: e.explanation for e in response.parsed_output.explanations}
    missing = {f.employee_id for f in facts} - explanations.keys()
    if missing:
        raise RuntimeError(f"No explanation for: {', '.join(sorted(missing))}")
    return explanations
