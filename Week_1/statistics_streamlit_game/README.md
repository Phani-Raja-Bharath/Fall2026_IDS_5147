# StatsQuest — Streamlit Statistics Game

This application converts the uploaded **Statistics for Modeling & Simulation**
notebook into an individual, self-paced Streamlit self-assessment.

## Game structure

1. **Center Stage**
   - Mean, median, mode
   - Effect of outliers

2. **Spread Detective**
   - Range / variability
   - Standard deviation
   - Same mean, different spread

3. **Distribution Dungeon**
   - Normal
   - Uniform
   - Bernoulli
   - Binomial

4. **Arrival Arena**
   - Poisson counts
   - Exponential interarrival times

5. **Monte Carlo Boss**
   - Airport security workload
   - Repeated simulation
   - Stability with increasing runs

## Gaming features

- Individual login (first name + last name + a self-chosen 4-digit PIN)
- XP scoring
- Level unlocking
- Badges
- Progression map
- Leaderboard
- Instant feedback
- Balloons for correct answers
- Final Monte Carlo boss level
- SQLite persistence
- Two attempts per challenge: a wrong first try gets one retry; a correct second try earns
  half-credit XP; a second wrong try reveals the correct answer and locks the challenge at 0 XP
- One bonus "make-up XP" challenge per level, worth the same XP as a regular challenge in that
  level, so a participant who lost XP to a retry has a way to earn it back before the next level unlocks
- Password-protected Admin Dashboard: full leaderboard, full attempt log, CSV export

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

or:

```bash
python -m streamlit run app.py
```

## Individual login

This is an **individual** challenge, not team-based. On first entry, each person types their
first name, last name, and picks their own 4-digit PIN. That name + PIN combination is their
login — using the exact same name and PIN again resumes their progress. The PIN exists so two
participants who happen to share a name don't collide into the same record, and so no one else
can casually view or answer for someone else.

There is no way to recover a forgotten PIN short of looking it up in the Admin Dashboard's
attempt log (matched by name) or clearing that person's rows from `stats_game.db` directly —
tell participants to remember their PIN.

## Admin Dashboard — checking scores

On the login screen, expand **"🛠️ Instructor / Admin access"** and enter the admin password to
reach the dashboard directly (no participant login needed). It shows:
- The full leaderboard (every participant, rank, XP, correct count, attempts) with CSV export
- The full attempt log (every answer, correct/incorrect, points, timestamp) with CSV export

**Set the admin password** before running a session — it defaults to `changeme123` otherwise:

```bash
# macOS/Linux
export STATSQUEST_ADMIN_PASSWORD="your-password-here"
streamlit run app.py
```

```powershell
# Windows PowerShell
$env:STATSQUEST_ADMIN_PASSWORD = "your-password-here"
streamlit run app.py
```

Scores persist in `stats_game.db` for as long as that file exists, so you can reopen the Admin
Dashboard at any time after the session — even after restarting the app — to review results.

## Deploying with Neon Postgres

For Streamlit Cloud, use Neon Postgres instead of local SQLite so scores persist after app
restarts and redeploys.

1. Create a free Neon project.
2. Copy the Neon pooled connection string.
3. In Streamlit Cloud, open the app settings and add this secret:

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST.neon.tech/DBNAME?sslmode=require"
```

The app automatically uses Neon when `DATABASE_URL` or `NEON_DATABASE_URL` is available.
Without either secret, it falls back to the local `stats_game.db` file.

For local development, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
and paste your real Neon connection string there. The real secrets file is ignored by git.
Keep using `DATABASE_URL` or `NEON_DATABASE_URL` for the database connection; `NEON_API_KEY`
is included only as a safe placeholder if you need to store that key locally later.

## Classroom suggestion

Give participants 20–30 minutes to work individually.

Suggested format:
- Project the leaderboard periodically (names only; no answer details are shown there)
- Debrief as a class by asking a few participants to explain an answer they had to retry

The database is created automatically as `stats_game.db`.
Delete this file before a new session if you want a clean leaderboard.
