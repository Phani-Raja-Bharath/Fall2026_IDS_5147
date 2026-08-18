MAX_WRONG_ATTEMPTS = 2
CONSOLATION_FRACTION = 0.5

LEVELS = {
    1: {"name": "Meanhaven Station", "icon": "🎯"},
    2: {"name": "Spreadmoor Yards", "icon": "📏"},
    3: {"name": "Distribution Junction", "icon": "🎲"},
    4: {"name": "Arrivals Terminal", "icon": "✈️"},
    5: {"name": "Simulation Lab", "icon": "🏆"},
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

CHALLENGE_NAMES = {
    "SRL_GOAL": "Personal Goal",
    "L1_PREDICT": "Outlier Prediction",
    "L1_OBSERVE": "Outlier Observation",
    "L1_OUTLIER": "Outlier Attack",
    "L1_CENTER": "Pick the Better Center",
    "L1_REFLECT": "Outlier Reflection",
    "L1_BONUS": "Level 1 Bonus",
    "L2_CONSISTENCY": "Machine Consistency",
    "L2_PREDICT_SD": "Spread Prediction",
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
