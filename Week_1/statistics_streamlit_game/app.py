import json
import math
import os
import random
import sqlite3
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

DB = "stats_game.db"

def get_secret(name):
    value = os.environ.get(name)
    if value:
        return value
    try:
        return st.secrets.get(name)
    except Exception:
        return None

DATABASE_URL = get_secret("DATABASE_URL") or get_secret("NEON_DATABASE_URL")
ADMIN_PASSWORD = get_secret("STATSQUEST_ADMIN_PASSWORD") or "changeme123"
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
}

.block-container {
    max-width: 1180px;
    padding-top: 1.4rem;
    padding-left: 1rem;
    padding-right: 1rem;
}

.game-title {
    font-size: clamp(1.65rem, 6vw, 2.1rem);
    line-height: 1.12;
    font-weight: 800;
    margin-bottom: 0.1rem;
}

.game-subtitle {
    color: #666;
    margin-bottom: 1rem;
    font-size: clamp(.95rem, 3vw, 1rem);
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

@media (max-width: 700px) {
    .block-container {
        padding-top: .75rem;
        padding-left: .75rem;
        padding-right: .75rem;
    }

    section[data-testid="stSidebar"] {
        min-width: min(88vw, 22rem);
    }

    div[data-testid="stHorizontalBlock"] {
        gap: .65rem;
    }

    div[data-testid="stHorizontalBlock"] > div {
        min-width: 100%;
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
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Database
# -----------------------------
def sql(sqlite_sql, postgres_sql=None):
    if USE_POSTGRES:
        return postgres_sql or sqlite_sql.replace("?", "%s")
    return sqlite_sql

class PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=None):
        cursor = self.connection.cursor()
        cursor.execute(query, params or ())
        return cursor

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()

def conn():
    if USE_POSTGRES:
        import psycopg2
        c = PostgresConnection(psycopg2.connect(DATABASE_URL))
    else:
        c = sqlite3.connect(DB, check_same_thread=False)
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
    c.commit()
    return c

def make_pid(first, last, pin):
    return f"{first.strip().lower()}|{last.strip().lower()}|{pin.strip()}"

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

def add_attempt(pid, level, challenge, answer, correct, points):
    c = conn()
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
    c.close()

def participant_stats(pid):
    c = conn()
    df = pd.read_sql_query(
        sql("SELECT * FROM challenge_attempts WHERE pid=? ORDER BY id"),
        c, params=(pid,)
    )
    c.close()
    return df

def leaderboard():
    c = conn()
    df = pd.read_sql_query("""
        SELECT p.pid AS PID,
               p.first_name || ' ' || p.last_name AS Name,
               COALESCE(SUM(a.points),0) AS XP,
               COALESCE(SUM(a.correct),0) AS Correct,
               COUNT(a.id) AS Attempts
        FROM participants p
        LEFT JOIN challenge_attempts a ON a.pid=p.pid
        GROUP BY p.pid
        ORDER BY XP DESC, Correct DESC, Attempts ASC
    """, c)
    c.close()
    if not df.empty:
        df.insert(0, "Rank", range(1, len(df)+1))
    return df

def level_score(pid, level):
    df = participant_stats(pid)
    if df.empty:
        return 0
    return int(df.loc[df.level == level, "points"].sum())

def total_xp(pid):
    df = participant_stats(pid)
    return 0 if df.empty else int(df.points.sum())

MAX_WRONG_ATTEMPTS = 2  # wrong tries allowed before the answer is revealed and the challenge locks

def challenge_history(pid, challenge):
    df = participant_stats(pid)
    if df.empty:
        return df
    return df[df.challenge == challenge]

# -----------------------------
# Game config
# -----------------------------
LEVELS = {
    1: {"name":"Center Stage", "icon":"🎯"},
    2: {"name":"Spread Detective", "icon":"📏"},
    3: {"name":"Distribution Dungeon", "icon":"🎲"},
    4: {"name":"Arrival Arena", "icon":"✈️"},
    5: {"name":"Monte Carlo Boss", "icon":"🏆"},
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

CHALLENGE_NAMES = {
    "L1_OUTLIER": "Outlier Attack",
    "L1_CENTER": "Pick the Better Center",
    "L1_BONUS": "Level 1 Bonus",
    "L2_CONSISTENCY": "Machine Consistency",
    "L2_SD": "Variability Lab",
    "L2_BONUS": "Level 2 Bonus",
    "L3_Q1": "Dungeon Door 1",
    "L3_Q2": "Dungeon Door 2",
    "L3_Q3": "Dungeon Door 3",
    "L3_Q4": "Dungeon Door 4",
    "L3_BONUS": "Bonus Door",
    "L4_POISSON": "Arrival Count",
    "L4_EXP": "Waiting Time",
    "L4_BONUS": "Level 4 Bonus",
    "L5_STABILITY": "Monte Carlo Stability",
    "L5_PURPOSE": "Monte Carlo Purpose",
    "L5_BONUS": "Variance Reduction Bonus",
}

PAGE_LEVELS = {
    "🎯 Level 1 — Center Stage": 1,
    "📏 Level 2 — Spread Detective": 2,
    "🎲 Level 3 — Distribution Dungeon": 3,
    "✈️ Level 4 — Arrival Arena": 4,
    "🏆 Level 5 — Monte Carlo Boss": 5,
}

PAGE_OPTIONS = [
    "🏠 Home",
    "🎯 Level 1 — Center Stage",
    "📏 Level 2 — Spread Detective",
    "🎲 Level 3 — Distribution Dungeon",
    "✈️ Level 4 — Arrival Arena",
    "🏆 Level 5 — Monte Carlo Boss",
    "🥇 Leaderboard",
]

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
    with st.expander("📺 Notebook YouTube resources", expanded=False):
        for title, url in resources:
            st.markdown(f"**{title}**")
            st.video(url)

def go_to_next_page():
    current = st.session_state.get("selected_page", PAGE_OPTIONS[0])
    current_index = PAGE_OPTIONS.index(current) if current in PAGE_OPTIONS else 0
    next_page = PAGE_OPTIONS[(current_index + 1) % len(PAGE_OPTIONS)]
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
    st.session_state.selected_page = next_page

def show_next_button():
    current = st.session_state.get("selected_page", PAGE_OPTIONS[0])
    current_index = PAGE_OPTIONS.index(current) if current in PAGE_OPTIONS else 0
    next_page = PAGE_OPTIONS[(current_index + 1) % len(PAGE_OPTIONS)]
    st.divider()
    st.button(f"Next: {next_page}", type="primary", on_click=go_to_next_page)

def boss_defeated_percent(xp):
    return min(100, round((xp / PERFECT_SCORE) * 100, 1))

def show_boss_progress(xp):
    defeated = boss_defeated_percent(xp)
    st.progress(min(1.0, xp / PERFECT_SCORE), text=f"Boss defeated: {defeated}%")
    if xp >= PERFECT_SCORE:
        st.success(f"👑 Perfect score: {xp}/{PERFECT_SCORE} XP. You defeated the Monte Carlo Boss!")
    else:
        st.info(f"Boss defeated: {defeated}% ({xp}/{PERFECT_SCORE} XP). A perfect score defeats the boss.")

def correct_challenges(pid):
    history = participant_stats(pid)
    if history.empty:
        return set()
    return set(history.loc[history["correct"] == 1, "challenge"].tolist())

def level_progress(pid, level):
    required = LEVEL_CHALLENGES[level]
    correct = correct_challenges(pid)
    answered = [challenge for challenge in required if challenge in correct]
    pending = [challenge for challenge in required if challenge not in correct]
    return len(answered), len(required), pending

def challenge_label(challenge):
    return CHALLENGE_NAMES.get(challenge, challenge)

def challenge_labels(challenges):
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
    level = first_incomplete_level(pid)
    if level is None:
        return "🥇 Leaderboard"
    for page, page_level in PAGE_LEVELS.items():
        if page_level == level:
            return page
    return "🏠 Home"

def page_accessible(pid, page):
    level = PAGE_LEVELS.get(page)
    if level is None:
        return page == "🏠 Home" or first_incomplete_level(pid) is None
    return all(level_complete(pid, earlier) for earlier in range(1, level))

def enforce_page_access(pid):
    selected_page = st.session_state.get("selected_page", PAGE_OPTIONS[0])
    if page_accessible(pid, selected_page):
        return selected_page
    fallback = first_incomplete_page(pid)
    st.session_state.selected_page = fallback
    set_answer_feedback("warning", "You need to answer all earlier level questions correctly before moving ahead.")
    st.rerun()

def show_level_progress(pid, level):
    required = LEVEL_CHALLENGES[level]
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

def set_answer_feedback(kind, message, balloons=False):
    st.session_state.answer_feedback = {"kind": kind, "message": message}
    st.session_state.show_balloons = balloons

def show_answer_feedback():
    feedback = st.session_state.get("answer_feedback")
    if not feedback:
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
    ("🥇 Monte Carlo Master", "250-504 XP", "Can reason through simulation uncertainty and boss-level Monte Carlo concepts."),
    ("👑 Simulation Champion", f"{PERFECT_SCORE} XP", "Perfect cumulative score; the Monte Carlo Boss is fully defeated."),
]

CONSOLATION_FRACTION = 0.5  # XP fraction awarded for a correct answer on the final attempt

def format_feedback(message, explanation=None):
    if explanation:
        return f"{message}\n\n**Why:** {explanation}"
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
            add_attempt(pid, level, challenge, answer, True, points)
            set_answer_feedback(
                "success",
                format_feedback(f"✅ Correct answer! +{points} XP (partial credit on your last try)", explanation),
                balloons=True,
            )
        elif attempt_number > MAX_WRONG_ATTEMPTS:
            add_attempt(pid, level, challenge, answer, True, 0)
            set_answer_feedback(
                "success",
                format_feedback("✅ Correct answer! No XP because the scoring attempts were already used, but this question is now complete.", explanation),
                balloons=True,
            )
        else:
            add_attempt(pid, level, challenge, answer, True, base)
            set_answer_feedback(
                "success",
                format_feedback(f"✅ Correct answer! +{base} XP", explanation),
                balloons=True,
            )
        st.rerun()
    else:
        add_attempt(pid, level, challenge, answer, False, 0)
        remaining = MAX_WRONG_ATTEMPTS - attempt_number
        if remaining > 0:
            consolation = max(5, int(base * CONSOLATION_FRACTION))
            message = format_feedback(
                f"❌ Not quite. {remaining} attempt(s) left "
                f"— a correct answer next time earns partial credit (+{consolation} XP).",
                explanation,
            )
            set_answer_feedback("warning", message)
            st.warning(message)
        else:
            reveal = f" The correct answer was **{correct_answer}**." if correct_answer is not None else ""
            message = format_feedback(
                f"❌ Not quite. Scoring attempts are used, so this challenge is now worth 0 XP.{reveal} Keep trying until you answer correctly to unlock the next page.",
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
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

conn().close()

if not st.session_state.logged:
    st.markdown('<div class="game-title">🎮 StatsQuest</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="game-subtitle">An individual statistics self-assessment for Modeling & Simulation</div>',
        unsafe_allow_html=True
    )

    st.info(
        "This is an individual challenge. Enter your name and choose a 4-digit PIN — "
        "use the same name + PIN next time to resume your progress. Keep your PIN "
        "private so no one else can see or change your scores."
    )

    c1, c2 = st.columns(2)
    first = c1.text_input("First name", placeholder="Ada")
    last = c2.text_input("Last name", placeholder="Lovelace")
    pin = st.text_input("Choose a 4-digit PIN", placeholder="1234", max_chars=4, type="password")

    if st.button("🚀 Enter StatsQuest", type="primary", use_container_width=True):
        if not first.strip() or not last.strip():
            st.warning("Enter your first and last name.")
        elif not pin.strip().isdigit() or len(pin.strip()) != 4:
            st.warning("Your PIN must be exactly 4 digits.")
        else:
            new_pid, fn, ln = register_participant(first, last, pin.strip())
            st.session_state.pid = new_pid
            st.session_state.first_name = fn
            st.session_state.last_name = ln
            st.session_state.logged = True
            st.rerun()

    with st.expander("🛠️ Instructor / Admin access"):
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
        st.dataframe(board, hide_index=True, use_container_width=True)
        st.download_button(
            "⬇️ Download leaderboard (CSV)",
            board.to_csv(index=False).encode("utf-8"),
            "statsquest_leaderboard.csv",
            "text/csv",
        )

    st.subheader("📜 Full attempt log")
    c = conn()
    log = pd.read_sql_query("""
        SELECT p.first_name || ' ' || p.last_name AS Name,
               a.level, a.challenge, a.answer, a.correct, a.points, a.created_at
        FROM challenge_attempts a
        JOIN participants p ON p.pid = a.pid
        ORDER BY a.created_at
    """, c)
    c.close()
    if log.empty:
        st.info("No attempts recorded yet.")
    else:
        st.dataframe(log, hide_index=True, use_container_width=True)
        st.download_button(
            "⬇️ Download attempt log (CSV)",
            log.to_csv(index=False).encode("utf-8"),
            "statsquest_attempts.csv",
            "text/csv",
        )

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

    selected = st.radio(
        "Game map",
        PAGE_OPTIONS,
        key="selected_page",
    )
    selected = enforce_page_access(pid)

    st.divider()
    if st.button("Log out"):
        st.session_state.logged = False
        st.rerun()

# -----------------------------
# Header
# -----------------------------
st.markdown('<div class="game-title">🎮 StatsQuest: Modeling & Simulation</div>', unsafe_allow_html=True)
st.caption("Learn statistics by working through challenges and unlocking levels.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("XP", f"{xp}/{PERFECT_SCORE}")
m2.metric("Badge", badge.split(" ",1)[0], badge.split(" ",1)[1] if " " in badge else "")
board = leaderboard()
rank = "—"
if not board.empty:
    pid_list = board["PID"].tolist()
    if pid in pid_list:
        rank = int(board["Rank"].tolist()[pid_list.index(pid)])
m3.metric("Boss Defeated", f"{boss_defeated_percent(xp)}%")
m4.metric("Class Rank", f"#{rank}" if rank != "—" else "—")

show_answer_feedback()

# -----------------------------
# Home / map
# -----------------------------
if selected == "🏠 Home":
    st.header("🗺️ Game Map")
    st.write(
        "Complete challenges to earn XP. Each level is based directly on the statistics topics "
        "from your Modeling & Simulation notebook."
    )
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
        "You must understand center, variability, probability distributions, "
        "arrival processes, and Monte Carlo simulation before defeating the final boss."
    )

    st.subheader("Badges")
    badge_df = pd.DataFrame(
        BADGE_DESCRIPTIONS,
        columns=["Badge", "Score needed", "What it means"],
    )
    st.dataframe(badge_df, hide_index=True, use_container_width=True)
    show_next_button()

# -----------------------------
# Level 1
# -----------------------------
elif selected == "🎯 Level 1 — Center Stage":
    st.header("🎯 Level 1 — Center Stage")
    show_level_progress(pid, 1)
    st.write("Dataset from the notebook: student commute times.")
    show_youtube_resources("level_1")

    data = [10, 15, 15, 20, 25, 30, 60]
    st.write(data)

    c1,c2,c3 = st.columns(3)
    c1.metric("Mean", f"{np.mean(data):.2f}")
    c2.metric("Median", f"{np.median(data):.0f}")
    c3.metric("Mode", "15")

    st.subheader("Challenge 1 — Outlier Attack")
    outlier = st.slider("Replace the final commute time with:", 60, 600, 600, 10)
    changed = [10,15,15,20,25,30,outlier]
    a,b = st.columns(2)
    a.metric("New mean", f"{np.mean(changed):.2f}")
    b.metric("New median", f"{np.median(changed):.2f}")

    q = st.radio(
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
    st.write("A hospital reports patient waiting times with a few extremely long delays.")
    q2 = st.radio(
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
    st.caption("Needed a retry above? Answer this for a chance to earn the XP back.")
    q3 = st.radio(
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
    show_next_button()

# -----------------------------
# Level 2
# -----------------------------
elif selected == "📏 Level 2 — Spread Detective":
    st.header("📏 Level 2 — Spread Detective")
    show_level_progress(pid, 2)
    show_youtube_resources("level_2")
    machine_a = np.array([9.9,10.0,10.0,10.0,10.1])
    machine_b = np.array([6,8,10,12,14])

    df = pd.DataFrame({
        "Machine":["A","B"],
        "Mean":[machine_a.mean(),machine_b.mean()],
        "Sample SD":[machine_a.std(ddof=1),machine_b.std(ddof=1)]
    })
    st.dataframe(df, hide_index=True, use_container_width=True)

    q = st.radio(
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
    spread = st.slider("Choose a standard deviation for a normal process", 1, 30, 10)
    np.random.seed(7)
    sample = np.random.normal(50, spread, 1200)
    hist = np.histogram(sample, bins=20)
    chart = pd.DataFrame({"Frequency": hist[0]}, index=np.round(hist[1][:-1],1))
    st.bar_chart(chart)

    q2 = st.radio(
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
    st.caption("Needed a retry above? Answer this for a chance to earn the XP back.")
    q3 = st.radio(
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
    show_next_button()

# -----------------------------
# Level 3
# -----------------------------
elif selected == "🎲 Level 3 — Distribution Dungeon":
    st.header("🎲 Level 3 — Distribution Dungeon")
    show_level_progress(pid, 3)
    st.write("Match each simulation situation to a probability distribution.")
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
        st.markdown(f"**Dungeon Door {i}:** {prompt}")
        ans = st.radio("Choose:", opts, key=cid)
        if st.button("Open door", key=f"{cid}_submit"):
            score_answer(
                pid,3,cid,ans,ans==correct,20,
                correct_answer=correct,
                explanation=distribution_explanations[cid],
            )

    st.subheader("🎁 Bonus Door — Make-Up XP")
    st.caption("Needed a retry on one of the doors above? Open this one for a chance to earn the XP back.")
    st.markdown("**Bonus Door:** The time between machine breakdowns is continuous and memoryless.")
    ans5 = st.radio("Choose:", ["Exponential","Binomial","Uniform"], key="L3_BONUS")
    if st.button("Open door", key="L3_BONUS_submit"):
        score_answer(
            pid,3,"L3_BONUS",ans5,ans5=="Exponential",20,
            correct_answer="Exponential",
            explanation="The Exponential distribution is continuous, memoryless, and commonly models time between events.",
        )
    show_next_button()

# -----------------------------
# Level 4
# -----------------------------
elif selected == "✈️ Level 4 — Arrival Arena":
    st.header("✈️ Level 4 — Arrival Arena")
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

    q1 = st.radio(
        "Which distribution models the NUMBER of passengers arriving in a fixed interval?",
        ["Poisson","Exponential","Normal"],
        key="l4q1"
    )
    if st.button("Lock count answer", key="l4submit1"):
        score_answer(
            pid,4,"L4_POISSON",q1,q1=="Poisson",35,
            correct_answer="Poisson",
            explanation="The Poisson distribution models how many events occur in a fixed interval when events happen at an average rate.",
        )

    mean_wait = 10/rate
    st.metric("Implied mean interarrival time", f"{mean_wait:.2f} min")

    q2 = st.radio(
        "Which distribution can model the TIME until the next passenger arrives?",
        ["Binomial","Exponential","Uniform"],
        key="l4q2"
    )
    if st.button("Lock waiting-time answer", key="l4submit2"):
        score_answer(
            pid,4,"L4_EXP",q2,q2=="Exponential",35,
            correct_answer="Exponential",
            explanation="The Exponential distribution models waiting time until the next event in a Poisson arrival process.",
        )

    st.subheader("🎁 Bonus Challenge — Make-Up XP")
    st.caption("Needed a retry above? Answer this for a chance to earn the XP back.")
    q3 = st.radio(
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
    show_next_button()

# -----------------------------
# Level 5
# -----------------------------
elif selected == "🏆 Level 5 — Monte Carlo Boss":
    st.header("🏆 Level 5 — Monte Carlo Boss")
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

    q1 = st.radio(
        "What usually happens to a Monte Carlo estimate as the number of runs increases?",
        [
            "It generally becomes more stable",
            "It always becomes larger",
            "It becomes deterministic after 100 runs"
        ],
        key="l5q1"
    )
    if st.button("Attack boss", key="l5submit1"):
        score_answer(
            pid,5,"L5_STABILITY",q1,
            q1=="It generally becomes more stable",45,
            correct_answer="It generally becomes more stable",
            explanation="More Monte Carlo runs average out random noise, so the estimate usually changes less from run to run.",
        )

    q2 = st.radio(
        "Why run Monte Carlo repeatedly instead of using only one random simulation?",
        [
            "To study the range and likelihood of possible outcomes",
            "To eliminate all uncertainty",
            "To guarantee the maximum possible result"
        ],
        key="l5q2"
    )
    if st.button("Final strike", key="l5submit2"):
        score_answer(
            pid,5,"L5_PURPOSE",q2,
            q2=="To study the range and likelihood of possible outcomes",45,
            correct_answer="To study the range and likelihood of possible outcomes",
            explanation="Monte Carlo repeats random simulations to estimate possible outcomes, their variation, and how likely they are.",
        )

    st.subheader("🎁 Bonus Challenge — Make-Up XP")
    st.caption("Needed a retry above? Answer this for a chance to earn the XP back.")
    q3 = st.radio(
        "What best describes a 'variance reduction' technique in Monte Carlo simulation?",
        [
            "A method to get more precise estimates with fewer runs",
            "A method that guarantees zero error",
            "A method that removes the need for randomness"
        ],
        key="l5q3"
    )
    if st.button("Bonus strike", key="l5submit3"):
        score_answer(
            pid,5,"L5_BONUS",q3,
            q3=="A method to get more precise estimates with fewer runs",45,
            correct_answer="A method to get more precise estimates with fewer runs",
            explanation="Variance reduction techniques reduce simulation noise, giving a more precise estimate for the same number of runs.",
        )

    show_boss_progress(xp)
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
        st.dataframe(board.drop(columns=["PID"]), hide_index=True, use_container_width=True)
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
            use_container_width=True
        )
    show_next_button()
