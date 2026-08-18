MAX_WRONG_ATTEMPTS = 2
CONSOLATION_FRACTION = 0.5

LEVELS = {
    1: {"name": "The Unusual Commute", "icon": "🎯"},
    2: {"name": "Same Average, Different Machines", "icon": "📏"},
    3: {"name": "Choose the Right Randomness", "icon": "🎲"},
    4: {"name": "Airport Arrival Lab", "icon": "✈️"},
    5: {"name": "The Simulation Decision", "icon": "🏆"},
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
    1: ["L1_PREDICT", "L1_OBSERVE", "L1_OUTLIER", "L1_CENTER", "L1_REFLECT", "L1_BONUS"],
    2: ["L2_CONSISTENCY", "L2_PREDICT_SD", "L2_SD", "L2_BONUS"],
    3: ["L3_Q1", "L3_Q2", "L3_Q3", "L3_Q4", "L3_BONUS"],
    4: ["L4_POISSON", "L4_EXP", "L4_BONUS"],
    5: ["L5_STABILITY", "L5_PURPOSE", "L5_BONUS"],
}

LEVEL_REQUIRED_CHALLENGES = {
    level: [challenge for challenge in challenges if not challenge.endswith("_BONUS")]
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

# Kept identical to the plain labels shown on each level's own page (just
# "Question 1", "Prediction", "Bonus Question", ...) rather than separate
# flavor names -- these strings appear in the progress bar's "Completed" /
# "Pending" captions, and having them not match what's on the page is
# itself a source of confusion.
CHALLENGE_NAMES = {
    "SRL_GOAL": "Personal Goal",
    "L1_PREDICT": "Prediction",
    "L1_OBSERVE": "Observation",
    "L1_OUTLIER": "Question 1",
    "L1_CENTER": "Question 2",
    "L1_REFLECT": "Reflection",
    "L1_BONUS": "Bonus Question",
    "L2_CONSISTENCY": "Question 1",
    "L2_PREDICT_SD": "Prediction",
    "L2_SD": "Question 2",
    "L2_BONUS": "Bonus Question",
    "L3_Q1": "Question 1",
    "L3_Q2": "Question 2",
    "L3_Q3": "Question 3",
    "L3_Q4": "Question 4",
    "L3_BONUS": "Bonus Question",
    "L4_POISSON": "Question 1",
    "L4_EXP": "Question 2",
    "L4_BONUS": "Bonus Question",
    "L5_STABILITY": "Question 1",
    "L5_PURPOSE": "Question 2",
    "L5_BONUS": "Bonus Question",
}

BADGE_DESCRIPTIONS = [
    ("🎒 Rookie Modeler", "0-49 XP", "Getting started."),
    ("⭐ Stats Explorer", "50-109 XP", "Understands center and basic spread."),
    ("🥉 Variability Scout", "110-179 XP", "Can compare spread and distributions."),
    ("🥈 Distribution Strategist", "180-249 XP", "Can match distributions to situations."),
    ("🥇 Monte Carlo Master", "250-504 XP", "Can reason about simulation results."),
    ("👑 Simulation Champion", f"{PERFECT_SCORE} XP", "Perfect score. All challenges complete."),
]


def badge_for_xp(xp: int) -> str:
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


def boss_defeated_percent(xp: int) -> float:
    return min(100, round((xp / PERFECT_SCORE) * 100, 1))


def challenge_label(challenge: str) -> str:
    return CHALLENGE_NAMES.get(challenge, challenge)


def challenge_labels(challenges: list[str] | set[str] | tuple[str, ...]) -> str:
    return ", ".join(challenge_label(challenge) for challenge in challenges)
