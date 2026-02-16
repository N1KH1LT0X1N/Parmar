from typing import Literal


Interest = Literal["high", "medium", "low", "none"]

# ---------- Keyword banks ----------
_NEGATIVE_TERMS = [
    "stop call", "do not call", "not interested", "wrong number",
    "do not contact", "remove my number", "don't call", "never call",
    "no thanks", "not looking",
]

_HIGH_TERMS = [
    "interested", "schedule", "site visit", "book", "budget", "timeline",
    "follow-up", "follow up", "ready to buy", "looking to buy", "shortlisted",
    "advance", "possession", "registry", "loan approved", "finalize",
    "when can", "visit the property",
]

_MEDIUM_TERMS = [
    "call later", "maybe", "thinking", "send details", "brochure",
    "not sure", "exploring", "just researching", "few months",
    "checking options", "compare", "send info", "information",
]

# Mumbai locality keywords for hot-lead qualification
_MUMBAI_LOCALITIES = [
    "juhu", "bandra", "andheri", "powai", "worli", "dadar", "malad",
    "goregaon", "colaba", "borivali", "kandivali", "thane", "navi mumbai",
    "chembur", "mulund", "vikhroli", "ghatkopar", "kurla", "santacruz",
    "vile parle", "lower parel", "marine drive", "malabar hill",
]

_BUDGET_KEYWORDS = [
    "bhk", "budget", "crore", "cr", "lakh", "lakhs",
    "timeline", "month", "week", "ready to move",
]


def classify_interest(text: str, ended_reason: str = "") -> Interest:
    """Classify lead interest level from call summary and end reason."""
    normalized = f"{text} {ended_reason}".lower()

    # Negative signals are highest priority
    if any(term in normalized for term in _NEGATIVE_TERMS):
        return "none"

    high_score = sum(1 for term in _HIGH_TERMS if term in normalized)
    medium_score = sum(1 for term in _MEDIUM_TERMS if term in normalized)

    if high_score >= 2:
        return "high"
    if high_score == 1 and medium_score >= 1:
        return "high"
    if high_score == 1 or medium_score >= 1:
        return "medium"
    if "voicemail" in normalized or "no answer" in normalized:
        return "low"
    return "low"


def is_hot_lead(interest_level: Interest, summary: str) -> bool:
    """Determine if a high-interest lead should trigger a manager notification."""
    if interest_level != "high":
        return False

    normalized = summary.lower()

    locality_hits = sum(1 for loc in _MUMBAI_LOCALITIES if loc in normalized)
    budget_hits = sum(1 for kw in _BUDGET_KEYWORDS if kw in normalized)

    # Hot if locality + budget context, or strong budget signals
    return (locality_hits >= 1 and budget_hits >= 1) or budget_hits >= 2
