import json
import math
import os
import random
import sqlite3
import threading
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "stats_game.db")

def get_secret(name):
    value = os.environ.get(name)
    if value:
        return value
    try:
        return st.secrets.get(name)
    except Exception:
        return None

DATABASE_URL = get_secret("DATABASE_URL") or get_secret("NEON_DATABASE_URL")
_ADMIN_PASSWORD_SECRET = get_secret("STATSQUEST_ADMIN_PASSWORD")
ADMIN_PASSWORD = _ADMIN_PASSWORD_SECRET or "changeme123"
ADMIN_PASSWORD_IS_DEFAULT = not _ADMIN_PASSWORD_SECRET
USE_POSTGRES = bool(DATABASE_URL)

st.set_page_config(
    page_title="StatsQuest: Modeling & Simulation",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------
# Styling
# -----------------------------
st.markdown("""
<style>
:root {
    --statsquest-card-border: rgba(120,120,120,.25);
    --statsquest-accent: #2563eb;
    --statsquest-accent-hover: #1d4ed8;
}

.block-container {
    max-width: 1180px;
    padding: 2rem 1.5rem 3rem;
}

.game-title {
    font-size: clamp(1.65rem, 6vw, 2.1rem);
    line-height: 1.25;
    font-weight: 800;
    margin: 0 0 .2rem;
    padding-top: .1rem;
}

.game-subtitle {
    color: rgba(128,128,128,.95);
    margin-bottom: 1.15rem;
    font-size: clamp(.95rem, 3vw, 1rem);
}

.mobile-topbar {
    display: none;
    color: #111827;
}

.level-card {
    border: 1px solid var(--statsquest-card-border);
    border-radius: 8px;
    padding: 14px;
    margin-bottom: 10px;
}

.big-score {
    font-size: clamp(1.5rem, 5vw, 2rem);
    font-weight: 800;
}

.small-muted {color:#777; font-size:.9rem;}

div[data-testid="stMetric"] {
    border: 1px solid var(--statsquest-card-border);
    border-radius: 8px;
    padding: .65rem .75rem;
}

div[data-testid="stMetricValue"] {
    font-size: clamp(1.2rem, 5vw, 1.85rem);
    line-height: 1.1;
}

div[data-testid="stDataFrame"] {
    overflow-x: auto;
}

div[data-testid="stAlert"] {
    border-radius: 8px;
}

div[data-testid="stTextInput"] input {
    min-height: 2.75rem;
}

div[data-testid="stButton"] > button[kind="primary"],
div[data-testid="stDownloadButton"] > button[kind="primary"] {
    background: var(--statsquest-accent);
    border-color: var(--statsquest-accent);
    color: #fff;
}

div[data-testid="stButton"] > button[kind="primary"]:hover,
div[data-testid="stDownloadButton"] > button[kind="primary"]:hover {
    background: var(--statsquest-accent-hover);
    border-color: var(--statsquest-accent-hover);
    color: #fff;
}

@media (max-width: 700px) {
    .block-container {
        padding: .75rem .75rem 2rem;
        max-width: 100%;
    }

    .game-title {
        font-size: clamp(1.35rem, 7vw, 1.65rem);
        margin-bottom: .35rem;
    }

    .game-subtitle {
        margin-bottom: .85rem;
    }

    .mobile-topbar {
        display: block;
        margin: -.75rem -.75rem .85rem;
        padding: .65rem .75rem;
        background: rgba(255,255,255,.98);
        border-bottom: 1px solid var(--statsquest-card-border);
    }

    .mobile-topbar-title {
        font-size: .98rem;
        font-weight: 800;
        line-height: 1.25;
        overflow-wrap: anywhere;
    }

    .mobile-topbar-meta {
        color: #666;
        font-size: .82rem;
        margin-top: .15rem;
    }

    section[data-testid="stSidebar"] {
        min-width: min(88vw, 22rem);
    }

    div[data-testid="stHorizontalBlock"] {
        gap: .65rem;
        flex-wrap: wrap;
    }

    div[data-testid="stHorizontalBlock"] > div {
        min-width: min(100%, 16rem);
        flex: 1 1 100%;
    }

    div[data-testid="stButton"] > button,
    div[data-testid="stDownloadButton"] > button {
        width: 100%;
        min-height: 2.8rem;
        white-space: normal;
    }

    div[role="radiogroup"] label {
        min-height: 2.65rem;
        align-items: flex-start;
        padding-top: .45rem;
        padding-bottom: .45rem;
    }

    .stSlider {
        padding-left: .15rem;
        padding-right: .15rem;
    }

    iframe {
        max-width: 100%;
    }
}

@media (max-width: 700px) and (prefers-color-scheme: dark) {
    .mobile-topbar {
        background: rgba(17,24,39,.98);
        color: #f9fafb;
    }

    .mobile-topbar-meta {
        color: #d1d5db;
    }
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Database
# -----------------------------
def sql(sqlite_sql, postgres_sql=None):
    if USE_POSTGRES:
        return postgres_sql or sqlite_sql.replace("?", "%s")
    return sqlite_sql

class DBConnection:
    """sqlite3.Connection-shaped wrapper over either the shared cached SQLite
    connection or a pooled Postgres connection, so the rest of the app stays
    agnostic to which backend is active.

    The underlying connection/pool is created once per process (see
    `_sqlite_connection` / `_postgres_pool` below) and reused across reruns
    instead of opening a brand-new network connection on every query.
    `close()` releases the connection back to its pool (Postgres) or is a
    no-op (SQLite, where the connection is long-lived) — callers keep calling
    it exactly as before.
    """

    def __init__(self, raw, *, lock=None, pool=None):
        self._raw = raw
        self._lock = lock
        self._pool = pool

    def _replace_postgres_connection(self):
        if self._pool is None:
            return False
        try:
            self._pool.putconn(self._raw, close=True)
        except Exception:
            pass
        self._raw = self._pool.getconn()
        return True

    def _is_postgres_connection_error(self, error):
        if self._pool is None:
            return False
        import psycopg2
        return isinstance(error, (psycopg2.OperationalError, psycopg2.InterfaceError))

    def execute(self, query, params=None):
        if self._lock is not None:
            with self._lock:
                return self._raw.execute(query, params or ())
        try:
            cursor = self._raw.cursor()
            cursor.execute(query, params or ())
            return cursor
        except Exception as error:
            if not self._is_postgres_connection_error(error):
                raise
            self._replace_postgres_connection()
            cursor = self._raw.cursor()
            cursor.execute(query, params or ())
            return cursor

    def cursor(self):
        return self._raw.cursor()

    def read_sql(self, query, params=None):
        """pandas.read_sql_query, but routed through the same write lock as
        execute()/commit(). pandas drives a non-SQLAlchemy connection via its
        own .cursor()/.execute() calls, which would otherwise bypass the lock
        entirely and let reads interleave with writes on the one shared
        SQLite connection."""
        if self._lock is not None:
            with self._lock:
                return pd.read_sql_query(query, self._raw, params=params)
        return pd.read_sql_query(query, self._raw, params=params)

    def commit(self):
        if self._lock is not None:
            with self._lock:
                self._raw.commit()
        else:
            try:
                self._raw.commit()
            except Exception as error:
                if not self._is_postgres_connection_error(error):
                    raise
                self._replace_postgres_connection()
                raise RuntimeError("Database connection was reset before commit. Please submit again.") from error

    def close(self):
        if self._pool is not None:
            self._pool.putconn(self._raw)
        # else: the shared SQLite connection stays open for the app's lifetime.

_sqlite_write_lock = threading.Lock()  # serializes writes on the one shared SQLite connection

@st.cache_resource(show_spinner=False)
def _sqlite_connection():
    """A single SQLite connection shared for the app's lifetime instead of
    reopening the database file on every helper call."""
    return sqlite3.connect(DB, check_same_thread=False)

@st.cache_resource(show_spinner=False)
def _postgres_pool():
    """A small connection pool shared for the app's lifetime instead of
    opening a new network connection to Postgres on every helper call."""
    from psycopg2.pool import ThreadedConnectionPool
    return ThreadedConnectionPool(
        1,
        10,
        DATABASE_URL,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )

def conn():
    if USE_POSTGRES:
        pool = _postgres_pool()
        db = DBConnection(pool.getconn(), pool=pool)
        db.execute("SELECT 1")
        return db
    return DBConnection(_sqlite_connection(), lock=_sqlite_write_lock)

@st.cache_resource(show_spinner=False)
def _ensure_schema():
    """Create the tables once per process instead of re-running two
    CREATE TABLE statements on every single conn() call."""
    c = conn()
    c.execute(sql("""
        CREATE TABLE IF NOT EXISTS participants(
            pid TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            pin TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """))
    c.execute(sql(
        """
        CREATE TABLE IF NOT EXISTS challenge_attempts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pid TEXT NOT NULL,
            level INTEGER NOT NULL,
            challenge TEXT NOT NULL,
            answer TEXT,
            correct INTEGER NOT NULL,
            points INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS challenge_attempts(
            id SERIAL PRIMARY KEY,
            pid TEXT NOT NULL,
            level INTEGER NOT NULL,
            challenge TEXT NOT NULL,
            answer TEXT,
            correct INTEGER NOT NULL,
            points INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
    ))
    # Guards against a race where two near-simultaneous submits (e.g. a fast
    # double-click) both pass the "not yet scored" check in score_answer()
    # before either has committed: only one row per (pid, challenge) is
    # allowed to have correct=1, so a second concurrent "correct" insert is
    # rejected by the database instead of silently doubling the XP.
    try:
        c.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_one_correct_per_challenge
            ON challenge_attempts(pid, challenge)
            WHERE correct = 1
        """)
    except Exception:
        pass  # pre-existing duplicate data (from before this guard existed) would block index creation
    c.commit()
    c.close()
    return True

def make_pid(first, last, pin):
    return f"{first.strip().lower()}|{last.strip().lower()}|{pin.strip()}"

def find_participant_pid_by_name(first, last):
    """Return the pid already registered under this name (any PIN), or None.
    Used to catch a mistyped PIN before it silently creates a duplicate,
    zero-XP identity for a returning student."""
    c = conn()
    row = c.execute(
        sql("SELECT pid FROM participants WHERE LOWER(first_name)=? AND LOWER(last_name)=?"),
        (first.strip().lower(), last.strip().lower())
    ).fetchone()
    c.close()
    return row[0] if row else None

def register_participant(first, last, pin):
    """Create (or resume) a participant identified by name + PIN. Returns (pid, first_name, last_name)."""
    pid = make_pid(first, last, pin)
    c = conn()
    row = c.execute(
        sql("SELECT first_name, last_name FROM participants WHERE pid=?"), (pid,)
    ).fetchone()
    if row:
        c.close()
        return pid, row[0], row[1]
    c.execute(
        sql("INSERT INTO participants VALUES(?,?,?,?,?)"),
        (pid, first.strip(), last.strip(), pin.strip(), datetime.now().isoformat(timespec="seconds"))
    )
    c.commit()
    c.close()
    return pid, first.strip(), last.strip()

def _is_duplicate_correct_attempt(error):
    """True if `error` is the unique-constraint violation from
    idx_one_correct_per_challenge (i.e. this challenge was already scored by
    a concurrent request), for either backend."""
    if isinstance(error, sqlite3.IntegrityError):
        return True
    if USE_POSTGRES:
        import psycopg2
        if isinstance(error, psycopg2.IntegrityError):
            return True
    return False

def add_attempt(pid, level, challenge, answer, correct, points):
    """Records an attempt. Returns False (instead of raising) if a
    concurrent request already recorded a correct answer for this
    (pid, challenge) first — see idx_one_correct_per_challenge."""
    c = conn()
    try:
        c.execute(
            sql("""INSERT INTO challenge_attempts(pid,level,challenge,answer,correct,points,created_at)
               VALUES(?,?,?,?,?,?,?)"""),
            (
                pid, level, challenge, str(answer),
                1 if correct else 0, int(points),
                datetime.now().isoformat(timespec="seconds")
            )
        )
        c.commit()
    except Exception as error:
        if correct and _is_duplicate_correct_attempt(error):
            return False
        raise
    finally:
        c.close()
    return True

def participant_stats(pid):
    c = conn()
    df = c.read_sql(
        sql("SELECT * FROM challenge_attempts WHERE pid=? ORDER BY id"),
        params=(pid,)
    )
    c.close()
    return df

def leaderboard():
    c = conn()
    # Aliases are double-quoted so Postgres preserves their exact case; unquoted
    # aliases (e.g. `AS PID`) get silently folded to lowercase on Postgres (but
    # not SQLite), which broke every `board["PID"]`-style lookup below whenever
    # the app ran against Postgres instead of the local SQLite file.
    df = c.read_sql("""
        SELECT p.pid AS "PID",
               p.first_name || ' ' || p.last_name AS "Name",
               COALESCE(SUM(a.points),0) AS "XP",
               COALESCE(SUM(a.correct),0) AS "Correct",
               COUNT(a.id) AS "Attempts"
        FROM participants p
        LEFT JOIN challenge_attempts a ON a.pid=p.pid
        GROUP BY p.pid
        ORDER BY "XP" DESC, "Correct" DESC, "Attempts" ASC
    """)
    c.close()
    if not df.empty:
        df.insert(0, "Rank", range(1, len(df)+1))
    return df

def level_score(pid, level):
    df = participant_stats(pid)
    if df.empty:
        return 0
    return int(df[df["level"] == level]["points"].sum())

def total_xp(pid):
    df = participant_stats(pid)
    return 0 if df.empty else int(df["points"].sum())

MAX_WRONG_ATTEMPTS = 2  # wrong tries allowed before the answer is revealed and the challenge locks

def challenge_history(pid, challenge):
    df = participant_stats(pid)
    if df.empty:
        return df
    return df[df["challenge"] == challenge]

# -----------------------------
# Pre/post learning assessment
# -----------------------------
# Reuses the same challenge_attempts table (level 0 = pre, level 6 = post,
# outside the 1-5 range used by real levels) so no schema change is needed.
# Always recorded at 0 XP: these are a diagnostic, not part of the game score.

def assessment_challenge_id(phase, key):
    return f"{'PRE' if phase == 'pre' else 'POST'}_{key}"

def assessment_level(phase):
    return 0 if phase == "pre" else 6

def record_diagnostic_answer(pid, phase, key, answer, correct):
    """Record a single, non-retryable diagnostic response."""
    challenge = assessment_challenge_id(phase, key)
    if not challenge_history(pid, challenge).empty:
        return  # already answered; diagnostic responses aren't retried
    add_attempt(pid, assessment_level(phase), challenge, answer, correct, 0)

def assessment_complete(pid, phase):
    history = participant_stats(pid)
    if history.empty:
        return False
    answered = set(history["challenge"].unique())
    required = {assessment_challenge_id(phase, key) for key, *_ in ASSESSMENT_QUESTIONS}
    return required.issubset(answered)

def assessment_score(pid, phase):
    total = len(ASSESSMENT_QUESTIONS)
    history = participant_stats(pid)
    if history.empty:
        return 0, total
    required = [assessment_challenge_id(phase, key) for key, *_ in ASSESSMENT_QUESTIONS]
    scored = history[history["challenge"].isin(required) & (history["correct"] == 1)]
    return int(scored["challenge"].nunique()), total

def self_assessment_summary(pid):
    total = len(SELF_ASSESSMENT_ITEMS)
    history = participant_stats(pid)
    if history.empty:
        return None, 0, total
    required = [assessment_challenge_id("pre", key) for key, _ in SELF_ASSESSMENT_ITEMS]
    rows = history[history["challenge"].isin(required)].copy()
    if rows.empty:
        return None, 0, total
    scores = rows["answer"].map(SELF_ASSESSMENT_VALUES).dropna()
    if scores.empty:
        return None, 0, total
    return float(scores.mean()), int(scores.count()), total

def show_assessment_review(pid, phase):
    history = participant_stats(pid)
    if history.empty:
        return
    if phase == "pre":
        st.subheader("Baseline self-assessment review")
        for key, prompt in SELF_ASSESSMENT_ITEMS:
            challenge = assessment_challenge_id("pre", key)
            row = history[history["challenge"] == challenge]
            if row.empty:
                continue
            answer = str(row.iloc[-1]["answer"])
            st.markdown(
                f"""
                <div class="level-card">
                    <b>{prompt}</b><br>
                    <span>{answer}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return
    phase_label = "Baseline" if phase == "pre" else "Check-out"
    st.subheader(f"{phase_label} review")
    for key, prompt, _, correct_answer in ASSESSMENT_QUESTIONS:
        challenge = assessment_challenge_id(phase, key)
        row = history[history["challenge"] == challenge]
        if row.empty:
            continue
        answer = str(row.iloc[-1]["answer"])
        is_correct = bool(row.iloc[-1]["correct"])
        status = "Correct" if is_correct else "Not quite"
        if is_correct:
            result = f"**{status}.** You chose **{answer}**."
        else:
            result = f"**{status}.** You chose **{answer}**; the best answer is **{correct_answer}**."
        st.markdown(
            f"""
            <div class="level-card">
                <b>{prompt}</b><br>
                <span>{result}</span><br>
                <span class="small-muted">{ASSESSMENT_EXPLANATIONS[key]}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

# -----------------------------
# Game config
# -----------------------------
LEVELS = {
    1: {"name":"Meanhaven Station", "icon":"🎯"},
    2: {"name":"Spreadmoor Yards", "icon":"📏"},
    3: {"name":"Distribution Junction", "icon":"🎲"},
    4: {"name":"Arrivals Terminal", "icon":"✈️"},
    5: {"name":"Simulation Lab", "icon":"🏆"},
}

LEVEL_MAX_POINTS = {
    1: 75,
    2: 90,
    3: 100,
    4: 105,
    5: 135,
}
PERFECT_SCORE = sum(LEVEL_MAX_POINTS.values())

LEVEL_CHALLENGES = {
    1: ["L1_OUTLIER", "L1_CENTER", "L1_BONUS"],
    2: ["L2_CONSISTENCY", "L2_SD", "L2_BONUS"],
    3: ["L3_Q1", "L3_Q2", "L3_Q3", "L3_Q4", "L3_BONUS"],
    4: ["L4_POISSON", "L4_EXP", "L4_BONUS"],
    5: ["L5_STABILITY", "L5_PURPOSE", "L5_BONUS"],
}

# The "*_BONUS" challenge in each level is presented to players as optional
# make-up credit, not a requirement — so it's excluded from what gates level
# completion / page progression. LEVEL_CHALLENGES (above) still lists it,
# since it's still scoreable and still counts toward LEVEL_MAX_POINTS /
# PERFECT_SCORE for players going for a perfect run.
LEVEL_REQUIRED_CHALLENGES = {
    level: [c for c in challenges if not c.endswith("_BONUS")]
    for level, challenges in LEVEL_CHALLENGES.items()
}

CHALLENGE_POINTS = {
    "L1_OUTLIER": 25,
    "L1_CENTER": 25,
    "L1_BONUS": 25,
    "L2_CONSISTENCY": 30,
    "L2_SD": 30,
    "L2_BONUS": 30,
    "L3_Q1": 20,
    "L3_Q2": 20,
    "L3_Q3": 20,
    "L3_Q4": 20,
    "L3_BONUS": 20,
    "L4_POISSON": 35,
    "L4_EXP": 35,
    "L4_BONUS": 35,
    "L5_STABILITY": 45,
    "L5_PURPOSE": 45,
    "L5_BONUS": 45,
}

CHALLENGE_NAMES = {
    "L1_OUTLIER": "Outlier Attack",
    "L1_CENTER": "Pick the Better Center",
    "L1_BONUS": "Level 1 Bonus",
    "L2_CONSISTENCY": "Machine Consistency",
    "L2_SD": "Variability Lab",
    "L2_BONUS": "Level 2 Bonus",
    "L3_Q1": "Junction Track 1",
    "L3_Q2": "Junction Track 2",
    "L3_Q3": "Junction Track 3",
    "L3_Q4": "Junction Track 4",
    "L3_BONUS": "Bonus Track",
    "L4_POISSON": "Arrival Count",
    "L4_EXP": "Waiting Time",
    "L4_BONUS": "Level 4 Bonus",
    "L5_STABILITY": "Monte Carlo Stability",
    "L5_PURPOSE": "Monte Carlo Purpose",
    "L5_BONUS": "Variance Reduction Bonus",
}

PAGE_LEVELS = {
    "🎯 Level 1 — Meanhaven Station": 1,
    "📏 Level 2 — Spreadmoor Yards": 2,
    "🎲 Level 3 — Distribution Junction": 3,
    "✈️ Level 4 — Arrivals Terminal": 4,
    "🏆 Level 5 — Simulation Lab": 5,
}

PAGE_OPTIONS = [
    "🧭 Diagnostic Check-In",
    "🏠 Home",
    "🎯 Level 1 — Meanhaven Station",
    "📏 Level 2 — Spreadmoor Yards",
    "🎲 Level 3 — Distribution Junction",
    "✈️ Level 4 — Arrivals Terminal",
    "🏆 Level 5 — Simulation Lab",
    "📊 Mastery Check-Out",
    "🥇 Leaderboard",
]

# Five questions mirroring the five levels, asked after Level 5 as a check-out.
# The baseline uses the same keys as a self-assessment, so completion checks and
# reporting can compare the same topics without treating the baseline as a quiz.
ASSESSMENT_QUESTIONS = [
    ("CENTER", "A dataset has one extremely large outlier. Which measure of center is pulled the most by it?",
     ["Mean", "Median", "Mode"], "Mean"),
    ("SPREAD", "Which single quantity best measures how spread out a dataset is around its mean?",
     ["Standard deviation", "Median", "Mode"], "Standard deviation"),
    ("DISTRIBUTION", "Which distribution models a fixed number of independent success/failure trials?",
     ["Binomial", "Uniform", "Exponential"], "Binomial"),
    ("ARRIVAL", "In a Poisson arrival process, which distribution models the time between two consecutive arrivals?",
     ["Exponential", "Normal", "Binomial"], "Exponential"),
    ("SIMULATION", "What is the main reason to run a Monte Carlo simulation many times instead of once?",
     ["To estimate the range and likelihood of outcomes", "To eliminate all randomness", "To guarantee the best-case result"],
     "To estimate the range and likelihood of outcomes"),
]

ASSESSMENT_EXPLANATIONS = {
    "CENTER": "The mean uses every value, so one extreme value can pull it far away from the typical data point.",
    "SPREAD": "Standard deviation measures how far values usually are from the mean.",
    "DISTRIBUTION": "A Binomial distribution counts successes across a fixed number of independent success/failure trials.",
    "ARRIVAL": "In a Poisson process, the time between events is modeled with an Exponential distribution.",
    "SIMULATION": "Many Monte Carlo runs show the range of possible outcomes and make estimates more stable.",
}

SELF_ASSESSMENT_SCALE = [
    "1 - I have not seen this yet",
    "2 - I recognize the idea, but I need help",
    "3 - I can try it with examples",
    "4 - I can explain it and use it",
    "5 - I could teach someone else",
]

SELF_ASSESSMENT_VALUES = {
    option: index
    for index, option in enumerate(SELF_ASSESSMENT_SCALE, start=1)
}

SELF_ASSESSMENT_ITEMS = [
    ("CENTER", "Choosing the best measure of center when data has outliers"),
    ("SPREAD", "Interpreting standard deviation as spread around the mean"),
    ("DISTRIBUTION", "Matching common distributions to modeling situations"),
    ("ARRIVAL", "Connecting Poisson event counts with Exponential waiting times"),
    ("SIMULATION", "Explaining why repeated Monte Carlo runs are useful"),
]

# -----------------------------
# Story
# -----------------------------
STORY = {
    "intro": (
        "**Mission:** fix five statistics problems and unlock the final simulation challenge.\n\n"
        "Start with a short confidence check-in. Then work through center, spread, distributions, "
        "arrival models, and Monte Carlo simulation. The final check-out lets you see what changed. "
        "Check-ins do not affect XP."
    ),
    "pre_assessment": (
        "Rate where you are starting on five statistics ideas. This is a self-assessment, not a quiz."
    ),
    "post_assessment": (
        "Answer five check-out questions to see what you can do after the game."
    ),
    "levels": {
        1: "Outliers can pull the mean. Compare mean, median, and mode before choosing a center.",
        2: "Two datasets can share the same mean but have very different spread.",
        3: "Match each modeling situation to the distribution that fits it.",
        4: "Use Poisson for event counts and Exponential for time between events.",
        5: "Run repeated simulations to estimate possible outcomes and uncertainty.",
    },
    "epilogue": (
        "Finished. You completed the statistics path and the final simulation challenge."
    ),
}

YOUTUBE_RESOURCES = {
    "home": [
        ("Notebook setup and statistics overview", "https://www.youtube.com/watch?v=iPy9Yisdlms"),
    ],
    "level_1": [
        ("Commute-time dataset", "https://www.youtube.com/watch?v=5gxzPkAQdIg"),
        ("Mean, median, and mode", "https://www.youtube.com/watch?v=KthQkeHZMLg"),
    ],
    "level_2": [
        ("Normal distribution and spread", "https://www.youtube.com/watch?v=A89FpnWX0rY"),
    ],
    "level_3": [
        ("Normal distribution", "https://www.youtube.com/watch?v=A89FpnWX0rY"),
        ("Uniform distribution", "https://www.youtube.com/watch?v=2nS3ltVimyU"),
        ("Binomial distribution", "https://www.youtube.com/watch?v=kI3gy6Efcew"),
    ],
    "level_4": [
        ("Poisson distribution", "https://www.youtube.com/watch?v=EXoLpIwM_Qc"),
        ("Poisson and Exponential connection", "https://www.youtube.com/watch?v=BELZStrWy2g"),
    ],
    "level_5": [
        ("Monte Carlo simulation", "https://www.youtube.com/watch?v=Q9Gy7mkk-2A"),
    ],
}

def show_youtube_resources(section_key):
    resources = YOUTUBE_RESOURCES.get(section_key, [])
    if not resources:
        return
    st.subheader("📺 Notebook YouTube resources")
    for title, url in resources:
        st.markdown(f"**{title}**")
        st.video(url)

def go_to_next_page():
    current = st.session_state.get("selected_page", PAGE_OPTIONS[0])
    current_index = PAGE_OPTIONS.index(current) if current in PAGE_OPTIONS else 0
    if current_index >= len(PAGE_OPTIONS) - 1:
        return
    next_page = PAGE_OPTIONS[current_index + 1]
    if current == "🧭 Diagnostic Check-In" and not assessment_complete(st.session_state.pid, "pre"):
        set_answer_feedback("warning", "Complete all 5 baseline self-ratings before heading out.")
        return
    if current == "📊 Mastery Check-Out" and not assessment_complete(st.session_state.pid, "post"):
        set_answer_feedback("warning", "Answer all 5 check-out questions before moving on.")
        return
    current_level = PAGE_LEVELS.get(current)
    if current_level and not level_complete(st.session_state.pid, current_level):
        answered, total, pending = level_progress(st.session_state.pid, current_level)
        set_answer_feedback(
            "warning",
            f"Complete this level before moving on. Correct answers: {answered}/{total}. Pending: {challenge_labels(pending)}.",
        )
        return
    if not page_accessible(st.session_state.pid, next_page):
        first_incomplete = first_incomplete_page(st.session_state.pid)
        st.session_state.selected_page = first_incomplete
        set_answer_feedback("warning", "You need to answer all earlier level questions correctly before moving ahead.")
        return
    st.session_state.answer_feedback = None
    st.session_state.selected_page = next_page

def show_next_button():
    current = st.session_state.get("selected_page", PAGE_OPTIONS[0])
    current_index = PAGE_OPTIONS.index(current) if current in PAGE_OPTIONS else 0
    if current_index >= len(PAGE_OPTIONS) - 1:
        return
    next_page = PAGE_OPTIONS[current_index + 1]
    st.divider()
    st.button(f"Next: {next_page}", type="primary", on_click=go_to_next_page)

def boss_defeated_percent(xp):
    return min(100, round((xp / PERFECT_SCORE) * 100, 1))

def show_boss_progress(xp):
    defeated = boss_defeated_percent(xp)
    st.progress(min(1.0, xp / PERFECT_SCORE), text=f"Final challenge progress: {defeated}%")
    if xp >= PERFECT_SCORE:
        st.success(f"👑 Perfect score: {xp}/{PERFECT_SCORE} XP. All challenges complete.")
    else:
        st.info(f"Progress: {defeated}% ({xp}/{PERFECT_SCORE} XP). A perfect score completes the path.")

def correct_challenges(pid):
    history = participant_stats(pid)
    if history.empty:
        return set()
    return set(history[history["correct"] == 1]["challenge"].tolist())

def level_progress(pid, level):
    """Progress against the level's REQUIRED challenges only — the bonus
    challenge is optional make-up credit and doesn't gate completion."""
    required = LEVEL_REQUIRED_CHALLENGES[level]
    correct = correct_challenges(pid)
    answered = [challenge for challenge in required if challenge in correct]
    pending = [challenge for challenge in required if challenge not in correct]
    return len(answered), len(required), pending

def level_bonus_challenge(level):
    """The single optional bonus challenge id for a level, or None."""
    required = set(LEVEL_REQUIRED_CHALLENGES[level])
    bonus_ids = [c for c in LEVEL_CHALLENGES[level] if c not in required]
    return bonus_ids[0] if bonus_ids else None

def level_has_wrong_required_attempt(pid, level):
    """True once the player has gotten at least one required question in
    this level wrong. The bonus challenge exists to make up for exactly
    that lost XP, so it only unlocks once there's something to make up."""
    history = participant_stats(pid)
    if history.empty:
        return False
    required = set(LEVEL_REQUIRED_CHALLENGES[level])
    wrong = history[history["challenge"].isin(required) & (history["correct"] == 0)]
    return not wrong.empty

def challenge_xp_missed(pid, challenge):
    base = CHALLENGE_POINTS.get(challenge, 0)
    if base == 0:
        return 0
    history = challenge_history(pid, challenge)
    if history.empty:
        return 0
    earned = int(history["points"].max())
    return max(0, base - earned)

def level_missed_required_xp(pid, level):
    return sum(challenge_xp_missed(pid, challenge) for challenge in LEVEL_REQUIRED_CHALLENGES[level])

def level_bonus_remaining_xp(pid, level):
    bonus_id = level_bonus_challenge(level)
    if bonus_id is None:
        return 0
    bonus_base = CHALLENGE_POINTS.get(bonus_id, 0)
    bonus_earned = 0
    history = challenge_history(pid, bonus_id)
    if not history.empty:
        bonus_earned = int(history["points"].max())
    return max(0, min(level_missed_required_xp(pid, level), bonus_base - bonus_earned))

def bonus_unlocked(pid, level):
    """Unlocked once a required question in this level has been missed, or
    once the bonus itself already has an attempt on record (so it doesn't
    vanish mid-attempt if later required answers all end up correct)."""
    bonus_id = level_bonus_challenge(level)
    if bonus_id is None:
        return False
    if level_has_wrong_required_attempt(pid, level):
        return True
    return not challenge_history(pid, bonus_id).empty

def challenge_label(challenge: str) -> str:
    return CHALLENGE_NAMES.get(challenge, challenge)

def challenge_labels(challenges) -> str:
    return ", ".join(challenge_label(challenge) for challenge in challenges)

def level_complete(pid, level):
    answered, total, _ = level_progress(pid, level)
    return answered == total

def first_incomplete_level(pid):
    for level in sorted(LEVEL_CHALLENGES):
        if not level_complete(pid, level):
            return level
    return None

def first_incomplete_page(pid):
    if not assessment_complete(pid, "pre"):
        return "🧭 Diagnostic Check-In"
    level = first_incomplete_level(pid)
    if level is None:
        return "📊 Mastery Check-Out" if not assessment_complete(pid, "post") else "🥇 Leaderboard"
    for page, page_level in PAGE_LEVELS.items():
        if page_level == level:
            return page
    return "🏠 Home"

def page_accessible(pid, page):
    if page == "🧭 Diagnostic Check-In":
        return True
    if not assessment_complete(pid, "pre"):
        return False  # the baseline check-in comes before everything else
    level = PAGE_LEVELS.get(page)
    if level is not None:
        return all(level_complete(pid, earlier) for earlier in range(1, level))
    if page == "📊 Mastery Check-Out":
        return level_complete(pid, 5)
    if page == "🥇 Leaderboard":
        return first_incomplete_level(pid) is None and assessment_complete(pid, "post")
    return page == "🏠 Home"

def enforce_page_access(pid):
    """Must be called before the `selected_page`-keyed radio widget is
    instantiated this run — Streamlit forbids writing to a widget's bound
    session_state key after that widget has already rendered in the same run."""
    selected_page = st.session_state.get("selected_page", PAGE_OPTIONS[0])
    if page_accessible(pid, selected_page):
        return
    fallback = first_incomplete_page(pid)
    st.session_state.selected_page = fallback
    set_answer_feedback("warning", "You need to answer all earlier level questions correctly before moving ahead.")
    st.rerun()

def show_level_progress(pid, level):
    required = LEVEL_REQUIRED_CHALLENGES[level]
    correct = correct_challenges(pid)
    answered_items = [challenge for challenge in required if challenge in correct]
    pending = [challenge for challenge in required if challenge not in correct]
    answered = len(answered_items)
    total = len(required)
    st.progress(answered / total, text=f"Correct answers: {answered}/{total}")
    if answered_items:
        st.caption(f"Answered correctly: {challenge_labels(answered_items)}")
    if pending:
        st.caption(f"Pending: {challenge_labels(pending)}")
    else:
        st.success("Level complete. You can move to the next page.")

    bonus_id = level_bonus_challenge(level)
    if bonus_id:
        missed_xp = level_missed_required_xp(pid, level)
        bonus_remaining = level_bonus_remaining_xp(pid, level)
        if missed_xp > 0:
            st.caption(f"Missed XP from required questions: {missed_xp}. Make-up XP still available here: {bonus_remaining}.")
        if bonus_id in correct:
            st.caption(f"🎁 Bonus complete: {challenge_label(bonus_id)} (+XP earned)")
        elif bonus_unlocked(pid, level):
            st.caption(f"🎁 Bonus unlocked: {challenge_label(bonus_id)} — a chance to earn back up to {bonus_remaining} XP.")
        else:
            st.caption(f"🎁 Bonus challenge locked — it unlocks if you miss a question above.")

def set_answer_feedback(kind, message, balloons=False):
    st.session_state.answer_feedback = {
        "kind": kind,
        "message": message,
        "page": st.session_state.get("selected_page"),
    }
    st.session_state.show_balloons = balloons

def show_answer_feedback():
    feedback = st.session_state.get("answer_feedback")
    if not feedback:
        return
    if feedback.get("page") != st.session_state.get("selected_page"):
        st.session_state.answer_feedback = None
        return
    kind = feedback.get("kind")
    message = feedback.get("message", "")
    if kind == "success":
        st.success(message)
    elif kind == "warning":
        st.warning(message)
    elif kind == "error":
        st.error(message)
    else:
        st.info(message)
    if st.session_state.get("show_balloons"):
        st.balloons()
        st.session_state.show_balloons = False

def badge_for_xp(xp):
    if xp >= PERFECT_SCORE:
        return "👑 Simulation Champion"
    if xp >= 250:
        return "🥇 Monte Carlo Master"
    if xp >= 180:
        return "🥈 Distribution Strategist"
    if xp >= 110:
        return "🥉 Variability Scout"
    if xp >= 50:
        return "⭐ Stats Explorer"
    return "🎒 Rookie Modeler"

BADGE_DESCRIPTIONS = [
    ("🎒 Rookie Modeler", "0-49 XP", "Starting the journey through statistics for modeling and simulation."),
    ("⭐ Stats Explorer", "50-109 XP", "Understands center and is beginning to reason about variability."),
    ("🥉 Variability Scout", "110-179 XP", "Can compare spread and recognize how distributions shape simulations."),
    ("🥈 Distribution Strategist", "180-249 XP", "Can connect probability distributions to modeling situations."),
    ("🥇 Monte Carlo Master", "250-504 XP", "Can reason through simulation uncertainty and Monte Carlo concepts."),
    ("👑 Simulation Champion", f"{PERFECT_SCORE} XP", "Perfect cumulative score; all challenges complete."),
]

CONSOLATION_FRACTION = 0.5  # XP fraction awarded for a correct answer on the final attempt

def shuffled_options(key, options):
    """Stable per-user option order so answers are randomized without rerun jitter."""
    shuffled = list(options)
    seed = f"{st.session_state.get('pid', 'anonymous')}|{key}"
    random.Random(seed).shuffle(shuffled)
    return shuffled

def answer_radio(label, options, key, **kwargs):
    return st.radio(label, shuffled_options(key, options), key=key, **kwargs)

def show_challenge_acknowledgement(pid, challenge):
    history = challenge_history(pid, challenge)
    if history.empty:
        return

    correct_rows = history[history["correct"] == 1]
    if not correct_rows.empty:
        row = correct_rows.iloc[-1]
        points = int(row["points"])
        answer = row["answer"]
        if points > 0:
            st.success(f"Answered: {challenge_label(challenge)}. You earned {points} XP. Your answer: {answer}.")
        else:
            st.info(f"Answered: {challenge_label(challenge)} is complete. No XP was available on this attempt. Your answer: {answer}.")
        return

    attempts_used = len(history)
    attempts_left = max(0, MAX_WRONG_ATTEMPTS - attempts_used)
    latest_answer = history.iloc[-1]["answer"]
    if attempts_left > 0:
        st.warning(
            f"Attempt recorded for {challenge_label(challenge)}. Last answer: {latest_answer}. "
            f"{attempts_left} scoring attempt(s) left."
        )
    else:
        st.warning(
            f"Scoring attempts used for {challenge_label(challenge)}. Last answer: {latest_answer}. "
            "Keep trying to complete the question."
        )

def format_correct_feedback(message, explanation=None):
    if explanation:
        return f"{message}\n\n**Why this is correct:** {explanation}"
    return message

def format_wrong_feedback(message, answer, correct_answer=None, explanation=None):
    details = []
    if answer is not None and correct_answer is not None:
        details.append(f"**Why this is wrong:** You chose **{answer}**, but the best answer is **{correct_answer}**.")
    elif answer is not None:
        details.append(f"**Why this is wrong:** **{answer}** is not the best choice here.")
    if explanation:
        details.append(f"**Why the correct answer works:** {explanation}")
    if details:
        return f"{message}\n\n" + "\n\n".join(details)
    return message

def score_answer(pid, level, challenge, answer, correct, base=20, correct_answer=None, explanation=None):
    history = challenge_history(pid, challenge)

    if not history.empty and (history["correct"] == 1).any():
        message = "You've already scored this challenge."
        set_answer_feedback("info", message)
        st.info(message)
        return

    wrong_so_far = len(history)  # every recorded attempt here is a wrong one
    attempt_number = wrong_so_far + 1
    is_final_attempt = attempt_number == MAX_WRONG_ATTEMPTS

    if correct:
        if is_final_attempt:
            points = max(5, int(base * CONSOLATION_FRACTION))
            recorded = add_attempt(pid, level, challenge, answer, True, points)
            success_message = format_correct_feedback(f"✅ Correct answer! +{points} XP (partial credit on your last try)", explanation)
        elif attempt_number > MAX_WRONG_ATTEMPTS:
            recorded = add_attempt(pid, level, challenge, answer, True, 0)
            success_message = format_correct_feedback("✅ Correct answer! No XP because the scoring attempts were already used, but this question is now complete.", explanation)
        else:
            recorded = add_attempt(pid, level, challenge, answer, True, base)
            success_message = format_correct_feedback(f"✅ Correct answer! +{base} XP", explanation)

        if recorded:
            set_answer_feedback("success", success_message, balloons=True)
        else:
            # A concurrent submit (e.g. a fast double-click) already scored
            # this challenge first — idx_one_correct_per_challenge rejected
            # this insert, so nothing was double-counted.
            set_answer_feedback("info", "You've already scored this challenge.")
        st.rerun()
    else:
        add_attempt(pid, level, challenge, answer, False, 0)
        remaining = MAX_WRONG_ATTEMPTS - attempt_number
        if remaining > 0:
            consolation = max(5, int(base * CONSOLATION_FRACTION))
            message = format_wrong_feedback(
                f"❌ Not quite. {remaining} attempt(s) left "
                f"— a correct answer next time earns partial credit (+{consolation} XP).",
                answer,
                correct_answer,
                explanation,
            )
            set_answer_feedback("warning", message)
            st.warning(message)
        else:
            reveal = f" The correct answer was **{correct_answer}**." if correct_answer is not None else ""
            message = format_wrong_feedback(
                f"❌ Not quite. Scoring attempts are used, so this challenge is now worth 0 XP.{reveal} Keep trying until you answer correctly to unlock the next page.",
                answer,
                correct_answer,
                explanation,
            )
            set_answer_feedback("error", message)
            st.error(message)

# -----------------------------
# Login
# -----------------------------
for key, default in {
    "logged": False,
    "is_admin": False,
    "pid": "",
    "first_name": "",
    "last_name": "",
    "answer_feedback": None,
    "show_balloons": False,
    "last_selected_page": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

_ensure_schema()

if not st.session_state.logged:
    st.markdown('<div class="game-title">🎮 StatsQuest</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="game-subtitle">An individual statistics self-assessment for Modeling & Simulation</div>',
        unsafe_allow_html=True
    )

    st.markdown(STORY["intro"])

    st.info(
        "Enter your name and a 4-digit PIN. Use the same name + PIN later to resume."
    )

    c1, c2 = st.columns(2)
    first = c1.text_input("First name", placeholder="Joe")
    last = c2.text_input("Last name", placeholder="Smith")
    pin = st.text_input("Choose a 4-digit PIN", placeholder="1234", max_chars=4, type="password")

    if st.button("🚀 Enter StatsQuest", type="primary", width="stretch"):
        if not first.strip() or not last.strip():
            st.warning("Enter your first and last name.")
        elif not pin.strip().isdigit() or len(pin.strip()) != 4:
            st.warning("Your PIN must be exactly 4 digits.")
        else:
            candidate_pid = make_pid(first, last, pin.strip())
            existing_pid = find_participant_pid_by_name(first, last)
            if existing_pid and existing_pid != candidate_pid:
                st.error(
                    "That name is already registered with a different PIN. "
                    "Enter the PIN you used the first time to resume your progress "
                    "(if you're a different person with the same name, add a middle "
                    "initial or ask your instructor for help)."
                )
            else:
                new_pid, fn, ln = register_participant(first, last, pin.strip())
                st.session_state.pid = new_pid
                st.session_state.first_name = fn
                st.session_state.last_name = ln
                st.session_state.selected_page = first_incomplete_page(new_pid)
                st.session_state.logged = True
                st.rerun()

    with st.expander("🛠️ Instructor / Admin access"):
        if ADMIN_PASSWORD_IS_DEFAULT:
            st.warning(
                "⚠️ No STATSQUEST_ADMIN_PASSWORD secret is set, so this app is using the "
                "built-in default admin password. Set that secret before sharing this app "
                "with students — the admin dashboard shows every participant's data."
            )
        admin_pw = st.text_input("Admin password", type="password", key="admin_pw_input")
        if st.button("Enter Admin Dashboard"):
            if admin_pw == ADMIN_PASSWORD:
                st.session_state.logged = True
                st.session_state.is_admin = True
                st.rerun()
            else:
                st.error("Incorrect admin password.")

    st.stop()

# -----------------------------
# Admin Dashboard
# -----------------------------
if st.session_state.is_admin:
    with st.sidebar:
        st.markdown("## 🛠️ Admin")
        if st.button("Log out"):
            st.session_state.logged = False
            st.session_state.is_admin = False
            st.rerun()

    st.markdown('<div class="game-title">🛠️ StatsQuest Admin Dashboard</div>', unsafe_allow_html=True)
    st.caption("Instructor view — every participant's score and full attempt history.")

    board = leaderboard()
    st.subheader("🥇 Leaderboard")
    if board.empty:
        st.info("No participants yet.")
    else:
        admin_board = board.drop(columns=["PID"])
        st.dataframe(admin_board, hide_index=True, width="stretch")
        st.download_button(
            "⬇️ Download leaderboard (CSV)",
            admin_board.to_csv(index=False).encode("utf-8"),
            "statsquest_leaderboard.csv",
            "text/csv",
        )

    st.subheader("📜 Full attempt log")
    c = conn()
    log = c.read_sql("""
        SELECT p.first_name || ' ' || p.last_name AS "Name",
               a.level, a.challenge, a.answer, a.correct, a.points, a.created_at
        FROM challenge_attempts a
        JOIN participants p ON p.pid = a.pid
        ORDER BY a.created_at
    """)
    c.close()
    if log.empty:
        st.info("No attempts recorded yet.")
    else:
        st.dataframe(log, hide_index=True, width="stretch")
        st.download_button(
            "⬇️ Download attempt log (CSV)",
            log.to_csv(index=False).encode("utf-8"),
            "statsquest_attempts.csv",
            "text/csv",
        )

    st.subheader("📈 Self-assessment and check-out")
    diag = log[log["challenge"].str.startswith(("PRE_", "POST_"))].copy() if not log.empty else log
    if diag.empty:
        st.info("No baseline or check-out responses recorded yet.")
    else:
        baseline = diag[diag["challenge"].str.startswith("PRE_")].copy()
        baseline["Confidence"] = baseline["answer"].map(SELF_ASSESSMENT_VALUES)
        baseline_summary = (
            baseline.dropna(subset=["Confidence"])
            .groupby("Name")
            .agg(
                **{
                    "Baseline confidence": ("Confidence", "mean"),
                    "Baseline topics": ("challenge", "nunique"),
                }
            )
        )
        checkout_summary = (
            diag[(diag["challenge"].str.startswith("POST_")) & (diag["correct"] == 1)]
            .groupby("Name")["challenge"]
            .nunique()
            .rename("Check-out correct")
        )
        summary = baseline_summary.join(checkout_summary, how="outer").fillna(
            {"Baseline topics": 0, "Check-out correct": 0}
        )
        if "Baseline confidence" in summary:
            summary["Baseline confidence"] = summary["Baseline confidence"].round(1)
        st.dataframe(summary.reset_index(), hide_index=True, width="stretch")

    st.stop()

pid = st.session_state.pid
xp = total_xp(pid)
badge = badge_for_xp(xp)

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.markdown(f"## 🙋 {st.session_state.first_name} {st.session_state.last_name}")
    st.metric("Total XP", f"{xp}/{PERFECT_SCORE}")
    st.write(badge)

    enforce_page_access(pid)  # may correct/rerun before the widget below is instantiated

    selected = st.radio(
        "Game map",
        PAGE_OPTIONS,
        key="selected_page",
    )

    st.divider()
    if st.button("Log out"):
        st.session_state.logged = False
        st.rerun()

# -----------------------------
# Header
# -----------------------------
if st.session_state.last_selected_page != selected:
    components.html(
        f"""
        <script>
        const token = {json.dumps(selected)};
        function scrollStatsQuestToTop() {{
            const win = window.parent;
            const doc = win.document;
            const selectors = [
                '[data-testid="stAppViewContainer"]',
                '[data-testid="stMain"]',
                'section.main',
                '.main',
                'body',
                'html'
            ];

            try {{
                win.scrollTo({{ top: 0, left: 0, behavior: "auto" }});
            }} catch (error) {{}}

            selectors.forEach((selector) => {{
                const element = doc.querySelector(selector);
                if (!element) return;
                try {{
                    element.scrollTop = 0;
                    element.scrollLeft = 0;
                    if (element.scrollTo) {{
                        element.scrollTo({{ top: 0, left: 0, behavior: "auto" }});
                    }}
                }} catch (error) {{}}
            }});
        }}

        scrollStatsQuestToTop();
        const requestFrame = window.parent.requestAnimationFrame || window.requestAnimationFrame;
        if (requestFrame) {{
            requestFrame(scrollStatsQuestToTop);
        }}
        [50, 150, 350, 700, 1200, 2500].forEach((delay) => {{
            window.setTimeout(scrollStatsQuestToTop, delay);
        }});
        </script>
        """,
        height=0,
    )
    st.session_state.last_selected_page = selected

st.markdown(
    f"""
    <div class="mobile-topbar">
        <div class="mobile-topbar-title">{selected}</div>
        <div class="mobile-topbar-meta">🎮 StatsQuest · {xp}/{PERFECT_SCORE} XP · {badge}</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown('<div class="game-title">🎮 StatsQuest: Modeling & Simulation</div>', unsafe_allow_html=True)
st.caption("Short statistics challenges with XP, progress, and a leaderboard.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("XP", f"{xp}/{PERFECT_SCORE}")
m2.metric("Badge", badge.split(" ",1)[0], badge.split(" ",1)[1] if " " in badge else "", delta_color="off")
board = leaderboard()
rank = "—"
if not board.empty:
    pid_list = board["PID"].tolist()
    if pid in pid_list:
        rank = int(board["Rank"].tolist()[pid_list.index(pid)])
m3.metric("Progress", f"{boss_defeated_percent(xp)}%")
m4.metric("Class Rank", f"#{rank}" if rank != "—" else "—")

show_answer_feedback()

# -----------------------------
# Pre-assessment (Diagnostic Check-In)
# -----------------------------
if selected == "🧭 Diagnostic Check-In":
    st.header("🧭 Diagnostic Check-In")
    st.markdown(STORY["pre_assessment"])

    if assessment_complete(pid, "pre"):
        avg_confidence, answered_count, total_count = self_assessment_summary(pid)
        if avg_confidence is None:
            st.success("Baseline recorded.")
        else:
            st.success(f"Baseline recorded: average confidence {avg_confidence:.1f}/5 across {answered_count}/{total_count} topics.")
        st.caption("This didn't affect your XP — it just gives us something to compare against once you finish.")
        show_assessment_review(pid, "pre")
    else:
        st.info(
            "Rate your current confidence before you head out to Meanhaven Station. "
            "There are no right or wrong answers and this won't affect your XP."
        )
        with st.form("pre_assessment_form"):
            pre_answers = {}
            for key, prompt in SELF_ASSESSMENT_ITEMS:
                pre_answers[key] = st.radio(prompt, SELF_ASSESSMENT_SCALE, key=f"pre_{key}", index=None)
            pre_submitted = st.form_submit_button("Submit self-assessment", type="primary")
        if pre_submitted:
            if any(value is None for value in pre_answers.values()):
                st.warning("Rate all 5 topics before submitting.")
            else:
                for key, _ in SELF_ASSESSMENT_ITEMS:
                    record_diagnostic_answer(pid, "pre", key, pre_answers[key], False)
                set_answer_feedback("success", "Self-assessment recorded. You can start Level 1.")
                st.rerun()
    show_next_button()

# -----------------------------
# Home / map
# -----------------------------
elif selected == "🏠 Home":
    st.header("🗺️ Game Map")
    st.markdown(STORY["intro"])
    show_youtube_resources("home")

    for level, info in LEVELS.items():
        accessible = page_accessible(pid, next(page for page, page_level in PAGE_LEVELS.items() if page_level == level))
        complete = level_complete(pid, level)
        answered, total, _ = level_progress(pid, level)
        if complete:
            status = "✅ Complete"
        elif accessible:
            status = "🟢 Available"
        else:
            status = "🔒 Locked until earlier questions are correct"
        earned = level_score(pid, level)
        st.markdown(
            f"""
            <div class="level-card">
                <b>{info['icon']} Level {level}: {info['name']}</b><br>
                <span class="small-muted">{status} · Correct answers: {answered}/{total} · XP earned here: {earned}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.subheader("Mission")
    st.write(
        "Complete the five levels: center, variability, distributions, arrivals, and Monte Carlo simulation."
    )
    if assessment_complete(pid, "pre"):
        avg_confidence, _, _ = self_assessment_summary(pid)
        if avg_confidence is None:
            st.caption("📈 Baseline self-assessment recorded.")
        else:
            st.caption(f"📈 Baseline confidence: {avg_confidence:.1f}/5 before training.")

    st.subheader("Badges")
    badge_df = pd.DataFrame(
        BADGE_DESCRIPTIONS,
        columns=["Badge", "Score needed", "What it means"],
    )
    st.dataframe(badge_df, hide_index=True, width="stretch")
    show_next_button()

# -----------------------------
# Level 1
# -----------------------------
elif selected == "🎯 Level 1 — Meanhaven Station":
    st.header("🎯 Level 1 — Meanhaven Station")
    st.markdown(STORY["levels"][1])
    show_level_progress(pid, 1)
    st.write("Dataset from the notebook: student commute times.")
    show_youtube_resources("level_1")

    data = [10, 15, 15, 20, 25, 30, 60]
    st.write(data)

    c1,c2,c3 = st.columns(3)
    c1.metric("Mean", f"{np.mean(data):.2f}")
    c2.metric("Median", f"{np.median(data):.0f}")
    modes = pd.Series(data).mode().tolist()
    c3.metric("Mode", ", ".join(str(int(m)) for m in modes))

    st.subheader("Challenge 1 — Outlier Attack")
    show_challenge_acknowledgement(pid, "L1_OUTLIER")
    outlier = st.slider("Replace the final commute time with:", 60, 600, 600, 10)
    changed = [10,15,15,20,25,30,outlier]
    a,b = st.columns(2)
    a.metric("New mean", f"{np.mean(changed):.2f}")
    b.metric("New median", f"{np.median(changed):.2f}")

    q = answer_radio(
        "Which statistic is affected more by the extreme outlier?",
        ["Mean", "Median", "Mode"],
        key="l1q1"
    )
    if st.button("Lock answer", key="l1submit1"):
        score_answer(
            pid,1,"L1_OUTLIER",q,q=="Mean",25,
            correct_answer="Mean",
            explanation="The mean uses every value in the calculation, so one extreme commute time pulls the average upward much more than it changes the median.",
        )

    st.subheader("Challenge 2 — Pick the Better Center")
    show_challenge_acknowledgement(pid, "L1_CENTER")
    st.write("A hospital reports patient waiting times with a few extremely long delays.")
    q2 = answer_radio(
        "Which measure would usually be more resistant to those extreme values?",
        ["Mean","Median","Range"],
        key="l1q2"
    )
    if st.button("Lock answer", key="l1submit2"):
        score_answer(
            pid,1,"L1_CENTER",q2,q2=="Median",25,
            correct_answer="Median",
            explanation="The median depends on the middle position after sorting, so a few extremely long waits do not distort it as strongly as they distort the mean.",
        )

    st.subheader("🎁 Bonus Challenge — Make-Up XP")
    if bonus_unlocked(pid, 1):
        st.caption("Optional — doesn't block moving on. A chance to earn back the XP you missed above.")
        show_challenge_acknowledgement(pid, "L1_BONUS")
        q3 = answer_radio(
            "A dataset is symmetric (bell-shaped) with no outliers. How do its mean and median compare?",
            ["They are approximately equal","The mean is always much larger","The median is undefined"],
            key="l1q3"
        )
        if st.button("Lock answer", key="l1submit3"):
            score_answer(
                pid,1,"L1_BONUS",q3,q3=="They are approximately equal",25,
                correct_answer="They are approximately equal",
                explanation="In a symmetric bell-shaped dataset, values balance around the center, so the mean and median usually land close together.",
            )
    else:
        st.caption("🔒 Unlocks if you miss a question above — it's here to help you make up lost XP.")
    show_next_button()

# -----------------------------
# Level 2
# -----------------------------
elif selected == "📏 Level 2 — Spreadmoor Yards":
    st.header("📏 Level 2 — Spreadmoor Yards")
    st.markdown(STORY["levels"][2])
    show_level_progress(pid, 2)
    show_youtube_resources("level_2")
    machine_a = np.array([9.9,10.0,10.0,10.0,10.1])
    machine_b = np.array([6,8,10,12,14])

    df = pd.DataFrame({
        "Machine":["A","B"],
        "Mean":[machine_a.mean(),machine_b.mean()],
        "Sample SD":[machine_a.std(ddof=1),machine_b.std(ddof=1)]
    })
    st.dataframe(df, hide_index=True, width="stretch")

    show_challenge_acknowledgement(pid, "L2_CONSISTENCY")
    q = answer_radio(
        "Both machines have the same mean. Which machine is more consistent?",
        ["Machine A","Machine B","They are equally consistent"],
        key="l2q1"
    )
    if st.button("Lock answer", key="l2submit1"):
        score_answer(
            pid,2,"L2_CONSISTENCY",q,q=="Machine A",30,
            correct_answer="Machine A",
            explanation="Machine A's values stay very close to 10, giving it a much smaller standard deviation and more consistent output.",
        )

    st.subheader("Variability Lab")
    show_challenge_acknowledgement(pid, "L2_SD")
    spread = st.slider("Choose a standard deviation for a normal process", 1, 30, 10)
    np.random.seed(7)
    sample = np.random.normal(50, spread, 1200)
    hist = np.histogram(sample, bins=20)
    chart = pd.DataFrame({"Frequency": hist[0]}, index=np.round(hist[1][:-1],1))
    st.bar_chart(chart)

    q2 = answer_radio(
        "As standard deviation increases, what happens to the distribution?",
        ["It becomes more spread out","It becomes narrower","The mean must increase"],
        key="l2q2"
    )
    if st.button("Lock answer", key="l2submit2"):
        score_answer(
            pid,2,"L2_SD",q2,q2=="It becomes more spread out",30,
            correct_answer="It becomes more spread out",
            explanation="Standard deviation measures typical distance from the mean; increasing it spreads observations farther away from the center.",
        )

    st.subheader("🎁 Bonus Challenge — Make-Up XP")
    if bonus_unlocked(pid, 2):
        st.caption("Optional — doesn't block moving on. A chance to earn back the XP you missed above.")
        show_challenge_acknowledgement(pid, "L2_BONUS")
        q3 = answer_radio(
            "Which quantity is the square of the standard deviation?",
            ["Variance","Mean","Median"],
            key="l2q3"
        )
        if st.button("Lock answer", key="l2submit3"):
            score_answer(
                pid,2,"L2_BONUS",q3,q3=="Variance",30,
                correct_answer="Variance",
                explanation="Variance is standard deviation squared; standard deviation is the square root of variance.",
            )
    else:
        st.caption("🔒 Unlocks if you miss a question above — it's here to help you make up lost XP.")
    show_next_button()

# -----------------------------
# Level 3
# -----------------------------
elif selected == "🎲 Level 3 — Distribution Junction":
    st.header("🎲 Level 3 — Distribution Junction")
    st.markdown(STORY["levels"][3])
    show_level_progress(pid, 3)
    st.write("Route each simulation situation onto the distribution that actually generates it.")
    show_youtube_resources("level_3")

    questions = [
        ("L3_Q1","Sensor measurement noise clustered around a target value",
         ["Normal","Poisson","Bernoulli"],"Normal"),
        ("L3_Q2","A success/failure event with probability p",
         ["Uniform","Bernoulli","Exponential"],"Bernoulli"),
        ("L3_Q3","Number of defective products among 20 independent products",
         ["Binomial","Normal","Uniform"],"Binomial"),
        ("L3_Q4","Every value between 0 and 100 is equally likely",
         ["Poisson","Uniform","Exponential"],"Uniform"),
    ]
    distribution_explanations = {
        "L3_Q1": "Normal distributions model continuous values that cluster around a central target with symmetric variation.",
        "L3_Q2": "Bernoulli distributions model one yes/no or success/failure trial with probability p.",
        "L3_Q3": "Binomial distributions count successes across a fixed number of independent Bernoulli trials.",
        "L3_Q4": "Uniform distributions give every value in the allowed interval the same chance.",
    }

    for i,(cid,prompt,opts,correct) in enumerate(questions,1):
        st.markdown(f"**Junction Track {i}:** {prompt}")
        show_challenge_acknowledgement(pid, cid)
        ans = answer_radio("Choose:", opts, key=cid)
        if st.button("Route signal", key=f"{cid}_submit"):
            score_answer(
                pid,3,cid,ans,ans==correct,20,
                correct_answer=correct,
                explanation=distribution_explanations[cid],
            )

    st.subheader("🎁 Bonus Track — Make-Up XP")
    if bonus_unlocked(pid, 3):
        st.caption("Optional — doesn't block moving on. A chance to earn back the XP you missed on a track above.")
        st.markdown("**Bonus Track:** The time between machine breakdowns is continuous and memoryless.")
        show_challenge_acknowledgement(pid, "L3_BONUS")
        ans5 = answer_radio("Choose:", ["Exponential","Binomial","Uniform"], key="L3_BONUS")
        if st.button("Route signal", key="L3_BONUS_submit"):
            score_answer(
                pid,3,"L3_BONUS",ans5,ans5=="Exponential",20,
                correct_answer="Exponential",
                explanation="The Exponential distribution is continuous, memoryless, and commonly models time between events.",
            )
    else:
        st.caption("🔒 Unlocks if you miss a track above — it's here to help you make up lost XP.")
    show_next_button()

# -----------------------------
# Level 4
# -----------------------------
elif selected == "✈️ Level 4 — Arrivals Terminal":
    st.header("✈️ Level 4 — Arrivals Terminal")
    st.markdown(STORY["levels"][4])
    show_level_progress(pid, 4)
    st.write(
        "The notebook connects Poisson event counts with Exponential interarrival times."
    )
    show_youtube_resources("level_4")

    rate = st.slider("Average passengers arriving per 10 minutes", 1, 20, 5)
    np.random.seed(11)
    counts = np.random.poisson(rate, 1000)
    values, freq = np.unique(counts, return_counts=True)
    st.bar_chart(pd.DataFrame({"Frequency":freq}, index=values))

    q1 = answer_radio(
        "Which distribution models the NUMBER of passengers arriving in a fixed interval?",
        ["Poisson","Exponential","Normal"],
        key="l4q1"
    )
    show_challenge_acknowledgement(pid, "L4_POISSON")
    if st.button("Lock count answer", key="l4submit1"):
        score_answer(
            pid,4,"L4_POISSON",q1,q1=="Poisson",35,
            correct_answer="Poisson",
            explanation="The Poisson distribution models how many events occur in a fixed interval when events happen at an average rate.",
        )

    mean_wait = 10/rate
    st.metric("Implied mean interarrival time", f"{mean_wait:.2f} min")

    q2 = answer_radio(
        "Which distribution can model the TIME until the next passenger arrives?",
        ["Binomial","Exponential","Uniform"],
        key="l4q2"
    )
    show_challenge_acknowledgement(pid, "L4_EXP")
    if st.button("Lock waiting-time answer", key="l4submit2"):
        score_answer(
            pid,4,"L4_EXP",q2,q2=="Exponential",35,
            correct_answer="Exponential",
            explanation="The Exponential distribution models waiting time until the next event in a Poisson arrival process.",
        )

    st.subheader("🎁 Bonus Challenge — Make-Up XP")
    if bonus_unlocked(pid, 4):
        st.caption("Optional — doesn't block moving on. A chance to earn back the XP you missed above.")
        show_challenge_acknowledgement(pid, "L4_BONUS")
        q3 = answer_radio(
            "If the average arrival rate doubles, what happens to the expected interarrival time (1/rate)?",
            ["It is halved","It doubles","It stays the same"],
            key="l4q3"
        )
        if st.button("Lock bonus answer", key="l4submit3"):
            score_answer(
                pid,4,"L4_BONUS",q3,q3=="It is halved",35,
                correct_answer="It is halved",
                explanation="Expected interarrival time is the reciprocal of the arrival rate, so doubling the rate cuts the expected wait in half.",
            )
    else:
        st.caption("🔒 Unlocks if you miss a question above — it's here to help you make up lost XP.")
    show_next_button()

# -----------------------------
# Level 5
# -----------------------------
elif selected == "🏆 Level 5 — Simulation Lab":
    st.header("🏆 Level 5 — Simulation Lab")
    st.markdown(STORY["levels"][5])
    show_level_progress(pid, 5)
    st.write(
        "Airport security workload: passenger count is Poisson and each passenger's "
        "service time is Exponential."
    )
    show_youtube_resources("level_5")

    arrivals = st.slider("Average arrivals / 10 min", 2, 20, 8)
    service = st.slider("Average service time (min)", 0.5, 4.0, 1.5, 0.1)
    runs = st.select_slider("Monte Carlo runs", options=[10,100,1000,10000], value=1000)

    seed = 42
    rng = np.random.default_rng(seed)
    workloads = []
    for _ in range(runs):
        n = rng.poisson(arrivals)
        if n == 0:
            workloads.append(0.0)
        else:
            workloads.append(rng.exponential(service, n).sum())
    workloads = np.array(workloads)

    a,b,c = st.columns(3)
    a.metric("Estimated mean", f"{workloads.mean():.2f}")
    b.metric("Std. deviation", f"{workloads.std(ddof=1):.2f}" if runs > 1 else "—")
    c.metric("95th percentile", f"{np.percentile(workloads,95):.2f}")

    hist = np.histogram(workloads, bins=min(30,max(5,int(math.sqrt(runs)))))
    st.bar_chart(pd.DataFrame({"Frequency":hist[0]}, index=np.round(hist[1][:-1],1)))

    q1 = answer_radio(
        "What usually happens to a Monte Carlo estimate as the number of runs increases?",
        [
            "It generally becomes more stable",
            "It always becomes larger",
            "It becomes deterministic after 100 runs"
        ],
        key="l5q1"
    )
    show_challenge_acknowledgement(pid, "L5_STABILITY")
    if st.button("Submit answer", key="l5submit1"):
        score_answer(
            pid,5,"L5_STABILITY",q1,
            q1=="It generally becomes more stable",45,
            correct_answer="It generally becomes more stable",
            explanation="More Monte Carlo runs average out random noise, so the estimate usually changes less from run to run.",
        )

    q2 = answer_radio(
        "Why run Monte Carlo repeatedly instead of using only one random simulation?",
        [
            "To study the range and likelihood of possible outcomes",
            "To eliminate all uncertainty",
            "To guarantee the maximum possible result"
        ],
        key="l5q2"
    )
    show_challenge_acknowledgement(pid, "L5_PURPOSE")
    if st.button("Submit final answer", key="l5submit2"):
        score_answer(
            pid,5,"L5_PURPOSE",q2,
            q2=="To study the range and likelihood of possible outcomes",45,
            correct_answer="To study the range and likelihood of possible outcomes",
            explanation="Monte Carlo repeats random simulations to estimate possible outcomes, their variation, and how likely they are.",
        )

    st.subheader("🎁 Bonus Challenge — Make-Up XP")
    if bonus_unlocked(pid, 5):
        st.caption("Optional — doesn't block moving on. A chance to earn back the XP you missed above.")
        show_challenge_acknowledgement(pid, "L5_BONUS")
        q3 = answer_radio(
            "What best describes a 'variance reduction' technique in Monte Carlo simulation?",
            [
                "A method to get more precise estimates with fewer runs",
                "A method that guarantees zero error",
                "A method that removes the need for randomness"
            ],
            key="l5q3"
        )
        if st.button("Submit bonus answer", key="l5submit3"):
            score_answer(
                pid,5,"L5_BONUS",q3,
                q3=="A method to get more precise estimates with fewer runs",45,
                correct_answer="A method to get more precise estimates with fewer runs",
                explanation="Variance reduction techniques reduce simulation noise, giving a more precise estimate for the same number of runs.",
            )
    else:
        st.caption("🔒 Unlocks if you miss a question above — it's here to help you make up lost XP.")

    show_boss_progress(xp)
    if xp >= PERFECT_SCORE:
        st.markdown(STORY["epilogue"])
    show_next_button()

# -----------------------------
# Post-assessment (Mastery Check-Out)
# -----------------------------
elif selected == "📊 Mastery Check-Out":
    st.header("📊 Mastery Check-Out")
    st.markdown(STORY["post_assessment"])

    if assessment_complete(pid, "post"):
        post_correct, post_total = assessment_score(pid, "post")
        avg_confidence, _, _ = self_assessment_summary(pid)
        st.success(f"Check-out recorded: {post_correct}/{post_total} correct.")
        a, b, c = st.columns(3)
        a.metric("Baseline confidence", f"{avg_confidence:.1f}/5" if avg_confidence is not None else "Recorded")
        b.metric("Check-out", f"{post_correct}/{post_total}")
        c.metric("Topics checked", f"{post_total}")
        show_assessment_review(pid, "post")
    else:
        st.info(
            "Five ungraded questions. No XP effect."
        )
        with st.form("post_assessment_form"):
            post_answers = {}
            for key, prompt, options, _ in ASSESSMENT_QUESTIONS:
                post_answers[key] = answer_radio(prompt, options, key=f"post_{key}", index=None)
            post_submitted = st.form_submit_button("Submit check-out", type="primary")
        if post_submitted:
            if any(value is None for value in post_answers.values()):
                st.warning("Answer all 5 questions before submitting.")
            else:
                for key, _, _, correct_answer in ASSESSMENT_QUESTIONS:
                    record_diagnostic_answer(pid, "post", key, post_answers[key], post_answers[key] == correct_answer)
                set_answer_feedback("success", "Check-out recorded. Here's how far you've come.")
                st.rerun()
    show_next_button()

# -----------------------------
# Leaderboard
# -----------------------------
elif selected == "🥇 Leaderboard":
    st.header("🥇 Class Leaderboard")
    board = leaderboard()
    if board.empty:
        st.info("No scores yet.")
    else:
        st.dataframe(board.drop(columns=["PID"]), hide_index=True, width="stretch")
        top = board.iloc[0]
        st.success(f"Current leader: {top['Name']} with {int(top['XP'])} XP")

    st.subheader("Your attempt history")
    history = participant_stats(pid)
    if history.empty:
        st.info("No scored attempts yet.")
    else:
        st.dataframe(
            history[["level","challenge","correct","points","created_at"]],
            hide_index=True,
            width="stretch"
        )
    show_next_button()
