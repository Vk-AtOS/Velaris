"""Deterministic reading of short business text: entities, the requested action, the subject domain.

Everything here is pattern and word-list matching. It recognises what it was
told to look for and nothing else; it does not understand language.
ponytail: English word lists, Indian number words (lakh, crore). Add lists per
language, or put a model in front (the agents accept one), when that falls short.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from velaris.intel import guard

_MULTIPLIER = {"k": 1e3, "thousand": 1e3, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "million": 1e6,
               "m": 1e6, "crore": 1e7, "crores": 1e7, "cr": 1e7}
_CURRENCY = {"₹": "INR", "rs": "INR", "rs.": "INR", "inr": "INR", "$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR"}
_AMOUNT = re.compile(
    r"(?P<cur>₹|\$|€|\b(?:rs\.?|inr|usd|eur)(?![a-z]))\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<mult>k|thousand|lakhs?|lac|million|m|crores?|cr)?\b", re.I)
_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PERCENT = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?%")
_REFERENCE = re.compile(r"\b[A-Z]{2,6}-\d{1,10}\b")
_WORD = re.compile(r"[a-z][a-z'-]*")
_MASK = re.compile(r"\[[A-Z_]+\]")          # placeholders left by guard.redact, e.g. [EMAIL]

# verb -> (canonical action, risk). "money" and "destructive" actions need a person's approval downstream.
ACTIONS: Dict[str, Tuple[str, str]] = {
    "approve": ("approve", "money"), "pay": ("pay", "money"), "refund": ("refund", "money"),
    "transfer": ("pay", "money"), "reimburse": ("pay", "money"), "purchase": ("purchase", "money"),
    "buy": ("purchase", "money"), "order": ("purchase", "money"),
    "delete": ("delete", "destructive"), "remove": ("delete", "destructive"), "cancel": ("cancel", "destructive"),
    "terminate": ("terminate", "destructive"), "revoke": ("revoke", "destructive"),
    "create": ("create", "normal"), "add": ("create", "normal"), "draft": ("create", "normal"),
    "update": ("update", "normal"), "change": ("update", "normal"), "edit": ("update", "normal"),
    "schedule": ("schedule", "normal"), "book": ("schedule", "normal"), "send": ("send", "normal"),
    "email": ("send", "normal"), "notify": ("send", "normal"), "assign": ("assign", "normal"),
    "deploy": ("deploy", "normal"), "hire": ("hire", "destructive"), "onboard": ("onboard", "normal"),
    "report": ("report", "read"), "summarise": ("report", "read"), "summarize": ("report", "read"),
    "show": ("report", "read"), "list": ("report", "read"), "find": ("search", "read"),
    "search": ("search", "read"), "check": ("report", "read"), "review": ("review", "read"),
}
_QUESTION_WORDS = {"what", "when", "where", "who", "whom", "why", "how", "which", "is", "are", "can", "could",
                   "does", "do", "did", "will", "would", "should"}
_NEGATIONS = {"not", "don't", "dont", "never", "no", "cannot", "can't", "won't", "stop"}
_URGENT = {"urgent", "urgently", "asap", "immediately", "critical", "emergency", "today"}
_STOP = {"the", "a", "an", "to", "for", "of", "and", "please", "kindly", "me", "my", "our", "this", "that",
         "in", "on", "by", "with", "from", "at", "all", "it", "us", "we", "i", "you", "need", "want"}

DOMAINS: Dict[str, Tuple[str, ...]] = {
    "finance": ("invoice", "payment", "budget", "expense", "tax", "gst", "ledger", "revenue", "payroll",
                "salary", "refund", "audit", "account", "accounts", "cash", "reimbursement", "tds"),
    "legal": ("contract", "agreement", "clause", "nda", "litigation", "compliance", "liability", "lawsuit",
              "court", "indemnity", "regulation", "statutory", "notice"),
    "medical": ("patient", "diagnosis", "prescription", "clinical", "hospital", "treatment", "symptom",
                "doctor", "dosage", "medical", "insurance claim"),
    "engineering": ("deploy", "server", "bug", "build", "release", "api", "database", "code", "outage",
                    "incident", "latency", "pipeline", "repository", "infrastructure"),
    "science": ("experiment", "hypothesis", "research", "laboratory", "sample", "study", "dataset", "analysis"),
    "governance": ("policy", "board", "risk", "approval", "governance", "control", "delegation", "oversight"),
    "psychology": ("wellbeing", "stress", "burnout", "morale", "counselling", "motivation", "behaviour"),
    "business": ("customer", "sales", "lead", "marketing", "campaign", "proposal", "vendor", "supplier",
                 "client", "deal", "hiring", "candidate", "employee", "leave", "onboarding", "strategy"),
}


def clean(text: str) -> str:
    """Fold look-alike characters, drop invisible ones, collapse whitespace."""
    return " ".join(guard.normalise(text).split())


def words(text: str) -> List[str]:
    return _WORD.findall(text.lower())


def entities(text: str) -> Dict[str, List[Any]]:
    """Typed values found in the text. Amounts come back as {"value", "currency"}."""
    amounts = []
    for m in _AMOUNT.finditer(text):
        value = float(m.group("num").replace(",", "")) * _MULTIPLIER.get((m.group("mult") or "").lower(), 1.0)
        amounts.append({"value": value, "currency": _CURRENCY[m.group("cur").lower()]})
    return {"amounts": amounts, "dates": _DATE.findall(text), "emails": _EMAIL.findall(text),
            "percentages": [float(p) for p in _PERCENT.findall(text)], "references": _REFERENCE.findall(text)}


def frame(text: str) -> Dict[str, Any]:
    """What a sentence asks for: act (question / command / statement), action verb, object words,
    negation, urgency and entities. `action` is None when no known verb appears."""
    cleaned = clean(text)
    found = entities(cleaned)
    bare = cleaned              # the sentence without its typed values, so they do not leak into `object`
    for pattern in (_AMOUNT, _DATE, _EMAIL, _PERCENT, _REFERENCE, _MASK):
        bare = pattern.sub(" ", bare)
    tokens = words(bare)
    verb_at = next((i for i, w in enumerate(tokens) if w in ACTIONS), None)
    action, risk = ACTIONS[tokens[verb_at]] if verb_at is not None else (None, None)
    is_question = cleaned.endswith("?") or (bool(tokens) and tokens[0] in _QUESTION_WORDS)
    obj: List[str] = []
    if verb_at is not None:
        obj = [w for w in tokens[verb_at + 1:] if w not in _STOP and w not in _URGENT and w not in _NEGATIONS][:6]
    return {
        "text": cleaned,
        "act": "question" if is_question else ("command" if action else "statement"),
        "action": action, "risk": risk, "object": " ".join(obj) or None,
        "negated": any(w in _NEGATIONS for w in (tokens[:verb_at] if verb_at is not None else tokens)),
        "urgent": any(w in _URGENT for w in tokens),
        "entities": found,
    }


def domain_scores(text: str) -> Dict[str, int]:
    """How many of each domain's terms appear in the text (whole words or phrases)."""
    lowered = " " + " ".join(words(text)) + " "
    return {d: sum(1 for term in terms if f" {term} " in lowered) for d, terms in DOMAINS.items()}


def best_domain(text: str) -> Tuple[Optional[str], float, Dict[str, int]]:
    """(domain, confidence, scores). No hit, or a tie for first place, gives domain None."""
    scores = domain_scores(text)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    total = sum(scores.values())
    if total == 0 or ranked[0][1] == ranked[1][1]:
        return None, 0.0, scores
    return ranked[0][0], round(ranked[0][1] / total, 3), scores
