# Fair-Schedule

AI-assisted restaurant scheduler that balances staff preferences fairly over time (Python, OR-Tools, Claude API).

## Planning context (Obsidian vault)

Early planning lives in my Obsidian vault, linked into this repo at `vault/` (a gitignored symlink to `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main`).

- Project note: `vault/Projects/Fair-Schedule/Fair-Schedule.md`: problem, user flow, behavior rules, scope, open decisions, day plan, decision log
- Idea note: `vault/Ideas/Fair-Schedule.md`
- Daily logs: `vault/Daily-logs/` (named `MM-DD-YYYY.md`)
- Concept notes: `vault/Notes/`

Follow the vault's own rules when reading or writing notes there:

@vault/CLAUDE.md

Current project plan:

@vault/Projects/Fair-Schedule/Fair-Schedule.md

## Source of truth

- The vault holds planning: open decisions, the decision log, and daily session logs. When a decision is made or the status changes, update the project note in the vault.
- Once specs exist, they live in this repo's `docs/` folder and the repo is the source of truth. The vault project note links to them; don't keep a second copy in the vault.
- Never write secrets or API keys to the repo or the vault. The Claude API key goes in `.env` / Streamlit secrets.
