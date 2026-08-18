PAGE_LEVELS = {
    "🎯 Level 1 — Meanhaven Station": 1,
    "📏 Level 2 — Spreadmoor Yards": 2,
    "🎲 Level 3 — Distribution Junction": 3,
    "✈️ Level 4 — Arrivals Terminal": 4,
    "🏆 Level 5 — Simulation Lab": 5,
}

PAGE_OPTIONS = [
    "🏠 Home",
    "🧭 Diagnostic Check-In",
    "🎯 Level 1 — Meanhaven Station",
    "📏 Level 2 — Spreadmoor Yards",
    "🎲 Level 3 — Distribution Junction",
    "✈️ Level 4 — Arrivals Terminal",
    "🏆 Level 5 — Simulation Lab",
    "📊 Mastery Check-Out",
    "🥇 Leaderboard",
]


def page_index(page: str) -> int:
    return PAGE_OPTIONS.index(page) if page in PAGE_OPTIONS else 0


def next_page(page: str) -> str | None:
    index = page_index(page)
    if index >= len(PAGE_OPTIONS) - 1:
        return None
    return PAGE_OPTIONS[index + 1]


def previous_page(page: str) -> str | None:
    index = page_index(page)
    if index <= 0:
        return None
    return PAGE_OPTIONS[index - 1]
