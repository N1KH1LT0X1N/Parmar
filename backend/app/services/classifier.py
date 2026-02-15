from typing import Literal


Interest = Literal["high", "medium", "low", "none"]


def classify_interest(text: str, ended_reason: str = "") -> Interest:
    normalized = f"{text} {ended_reason}".lower()

    if any(term in normalized for term in ["stop call", "do not call", "not interested", "wrong number"]):
        return "none"

    high_terms = ["interested", "schedule", "site visit", "book", "budget", "timeline", "follow-up"]
    medium_terms = ["call later", "maybe", "thinking", "send details"]

    high_score = sum(1 for term in high_terms if term in normalized)
    medium_score = sum(1 for term in medium_terms if term in normalized)

    if high_score >= 2:
        return "high"
    if high_score == 1 or medium_score >= 1:
        return "medium"
    if "voicemail" in normalized:
        return "low"
    return "low"


def is_hot_lead(interest_level: Interest, summary: str) -> bool:
    if interest_level != "high":
        return False

    normalized = summary.lower()
    qualifiers = [
        "juhu", "bandra", "andheri", "powai", "worli", "dadar", "malad", "goregaon", "colaba",
        "bhk", "budget", "crore", "lakh", "timeline", "month", "week"
    ]
    hits = sum(1 for q in qualifiers if q in normalized)
    return hits >= 2
