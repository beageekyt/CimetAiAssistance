"""Server-side safety net that scans transcript text for escalation signals.
The LLM is asked to call `escalate_to_human` itself, but we also scan every
utterance here so nothing slips through if the model misses it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .validate import contains_card_number

ANGER_WORDS = [
    "furious", "angry", "ridiculous", "unacceptable", "sick of", "fed up",
    "shouting", "yelling", "scam", "rip off", "rip-off", "sue", "lawyer",
]
CONFUSION_WORDS = [
    "i don't understand", "what do you mean", "confused", "i'm lost",
    "say that again", "not making sense", "huh?",
]
HUMAN_REQUEST_WORDS = [
    "talk to a person", "speak to a person", "speak to someone", "human being",
    "real person", "talk to a human", "representative", "manager", "supervisor",
]
ADVICE_WORDS = [
    "which plan is best", "what should i do", "what do you recommend",
    "give me advice", "which one should i pick", "what's better for me",
]
SENSITIVE_WORDS = [
    "life support", "life-support", "medical equipment", "hardship", "can't afford",
    "cannot afford", "domestic violence", "vulnerable", "disability", "payment dispute",
    "already paid", "dispute this bill",
]
DECLINE_WORDS = [
    "not interested", "stop calling", "remove me", "no thank you", "don't call again",
]


@dataclass
class SignalResult:
    escalate: bool
    reason: Optional[str] = None
    category: Optional[str] = None


def _any(text: str, words: list[str]) -> bool:
    t = text.lower()
    return any(w in t for w in words)


def scan_utterance(text: str) -> SignalResult:
    if contains_card_number(text):
        return SignalResult(escalate=False, category="card_data", reason="Card number detected; redirect to secure link.")
    if _any(text, SENSITIVE_WORDS):
        return SignalResult(escalate=True, category="sensitive", reason="Sensitive/vulnerability topic detected.")
    if _any(text, HUMAN_REQUEST_WORDS):
        return SignalResult(escalate=True, category="human_request", reason="Customer asked for a human.")
    if _any(text, ANGER_WORDS):
        return SignalResult(escalate=True, category="anger", reason="Anger/frustration detected.")
    if _any(text, ADVICE_WORDS):
        return SignalResult(escalate=True, category="advice", reason="Customer asked for personal advice.")
    if _any(text, CONFUSION_WORDS):
        return SignalResult(escalate=False, category="confusion", reason="Confusion detected.")
    if _any(text, DECLINE_WORDS):
        return SignalResult(escalate=False, category="decline", reason="Customer wants to opt out.")
    return SignalResult(escalate=False)


MAX_FIELD_ATTEMPTS = 3
