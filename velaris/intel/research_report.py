"""Report checking for the research pipeline: the part that is code, not model.

The model drafts the answer; this module decides what survives:

  check_claim()      does a claim follow from the passage quoted for it, as far
                     as code can tell without a model: its figures, dates and
                     names must be in the quote and it must not flip a negation.
  verify_report()    every sentence or bullet that says something must carry a
                     citation [n] whose number is in the registry. Unknown
                     numbers are deleted; a sentence left with no citation, or
                     with a figure that none of its cited sources contains, is
                     cut from the body and returned in `unsupported`.
  findings_body()    the answer built without a model: one bullet per verified
                     learning. Used when the model's draft is missing or empty
                     after checking.
  sources_section()  the numbered source list, generated from the registry so
                     a model can never invent or renumber a source.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

_CITE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_LEADING_CITES = re.compile(r"(?:\[[\d,\s]+\]\s*)+")
_LIST_MARKER = re.compile(r"\s*(?:[-*+]|\d+[.)])\s+")
_OWN_SOURCES = re.compile(r"^#+\s*(sources|references|citations|bibliography)\b", re.I | re.M)
# ponytail: sentence ends are guessed from punctuation followed by a capital, so
# "e.g. The" splits early. The error is on the safe side: the uncited fragment is
# removed. Use a real sentence tokenizer if good sentences are being lost.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(*\[])")


def _sentences(text: str) -> List[str]:
    out: List[str] = []
    for part in _SENTENCE_END.split(text):
        lead = _LEADING_CITES.match(part)
        if lead and out:          # "Claim. [1] Next" - the citation belongs to the sentence before it
            out[-1] += " " + lead.group(0).strip()
            part = part[lead.end():]
        if part.strip():
            out.append(part.strip())
    return out


def _keep_valid(sentence: str, valid: Set[int]) -> Tuple[str, bool]:
    """Delete citation numbers that are not in the registry. Returns (sentence, has a valid citation)."""
    found = False

    def fix(m: "re.Match[str]") -> str:
        nonlocal found
        good = [n for n in re.findall(r"\d+", m.group(1)) if int(n) in valid]
        found = found or bool(good)
        return "[" + ", ".join(good) + "]" if good else ""

    cleaned = _CITE.sub(fix, sentence)
    return re.sub(r"\s+([.,;:!?])", r"\1", re.sub(r"  +", " ", cleaned)).strip(), found


_NUMBER = re.compile(r"(\d[\d,]*(?:\.\d+)?)(?:\s*(thousand|million|billion|trillion)\b)?", re.I)
_SCALE = {"thousand": 10 ** 3, "million": 10 ** 6, "billion": 10 ** 9, "trillion": 10 ** 12}
_WORD_NUMBERS = {w: str(i) for i, w in enumerate(
    "two three four five six seven eight nine ten eleven twelve".split(), start=2)}
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MONTHS = "january february march april may june july august september october november december".split()
_MONTH = re.compile(r"\b(?:(january|february|march|april|june|july|august|september|october|november|december)"
                    r"|(jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)\.?(?=\s+\d)"
                    r"|(?<=\d\s)(jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec))\b", re.I)
_NEGATION = re.compile(r"\b(?:not|no|never|none|neither|nor|without|cannot)\b(?!\.\s*\d)|n['\u2019]t\b", re.I)
_NAME = re.compile(r"[A-Z][A-Za-z0-9&\u2019'-]*")
_NOT_NAMES = {m.capitalize() for m in _MONTHS} | {
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "I"}


def figures(text: str) -> Set[str]:
    """Every number and month named in the text, in one comparable form.

    "1,000", "1000.0" and "1 thousand" are the same figure; "two" to "twelve" count as
    digits; 2026-11-12 is read as 12 November 2026. Units and currencies are not compared.
    """
    text = _CITE.sub(" ", text)
    text = _ISO_DATE.sub(lambda m: f"{int(m.group(3))} {_MONTHS[int(m.group(2)) - 1]} {m.group(1)}"
                         if 1 <= int(m.group(2)) <= 12 else m.group(0), text)
    text = re.sub(r"\b(" + "|".join(_WORD_NUMBERS) + r")\b", lambda m: _WORD_NUMBERS[m.group(1).lower()],
                  text, flags=re.I)
    found: Set[str] = set()
    for digits, scale in _NUMBER.findall(text):
        try:
            value = Decimal(digits.replace(",", "")) * _SCALE.get(scale.lower(), 1)
        except InvalidOperation:
            continue
        found.add(format(value.normalize(), "f"))
    for m in _MONTH.finditer(text):
        found.add(next(g for g in m.groups() if g).lower()[:3])
    return found


def _names(claim: str) -> List[str]:
    """Capitalised words that look like names. The first word of a sentence is a name only if
    it is an acronym, has a digit or inner capital, or is followed by another capitalised word."""
    out: List[str] = []
    for sentence in _SENTENCE_END.split(claim):
        words = sentence.split()
        for i, raw in enumerate(words):
            m = _NAME.match(raw.lstrip("\"'([\u201c\u2018"))
            if not m:
                continue
            word = re.sub(r"['\u2019]s$", "", m.group(0)).rstrip("-'\u2019")
            if word in _NOT_NAMES or len(word) < 2:
                continue
            next_capital = i + 1 < len(words) and words[i + 1][:1].isupper()
            looks_like_name = word.isupper() or any(c.isdigit() or c.isupper() for c in word[1:]) or next_capital
            if i > 0 or looks_like_name:
                out.append(word)
    return list(dict.fromkeys(out))


def _has_word(word: str, text: str) -> bool:
    return re.search(r"(?<![A-Za-z0-9])" + re.escape(word) + r"(?![A-Za-z0-9])", text, re.I) is not None


def check_claim(claim: str, quote: str, context: str = "") -> Tuple[List[str], List[str]]:
    """Does the claim follow from the quote, as far as code can tell? Returns (problems, cautions).

    A problem means the claim says something its quote does not, and the claim should be dropped:
      - a number, date or month in the claim that is not in the quote;
      - the claim negates and the quote does not, or the other way round;
      - a name in the claim that is in neither the quote nor `context` (the rest of the source).
    A caution means it could not be settled either way and a person or a model should look:
      - a name that is in `context` but not in the quote itself.

    Limits. This compares surface features; it does not understand either sentence. It cannot
    see a wrong relation between right words ("A bought B" from "B bought A"), a changed unit or
    currency, a number worked out from others (a sum, a count, "half"), or a negation written
    without a negation word ("refused", "lacks", "free of"). It errs towards dropping: a true
    claim that rounds a figure, counts items, writes "500" for "five hundred", or rewords "no
    fees" as "free" is dropped too. A one-word name that opens a claim cannot be told from an
    ordinary capitalised word and is not checked. A claim that passes is not proven, only not caught.
    """
    problems: List[str] = []
    cautions: List[str] = []
    missing = sorted(figures(claim) - figures(quote))
    if missing:
        problems.append(f"figure not in the quote: {', '.join(missing)}")
    if bool(_NEGATION.search(claim)) != bool(_NEGATION.search(quote)):
        problems.append("the claim and the quote do not agree on a negation")
    for name in _names(claim):
        if _has_word(name, quote):
            continue
        if context and _has_word(name, context):
            cautions.append(f"'{name}' is named in the source but not in the quote")
        else:
            problems.append(f"name not in the source: {name}")
    return problems, cautions


def verify_report(body: str, valid: Set[int],
                  evidence: Optional[Dict[int, str]] = None) -> Tuple[str, List[str]]:
    """Keep only cited statements. Returns (checked body, sentences that were removed).

    Headings and lines with no words pass through; they are layout. Everything
    else is split into sentences and each one needs a citation of its own.
    With `evidence` (citation number -> the text that source supplied), a sentence
    is also removed when it states a figure that none of the sources it cites
    contains. The limits of that comparison are those listed under check_claim.
    """
    own = _OWN_SOURCES.search(body)
    if own:                       # the source list is written by code, never by the model
        body = body[:own.start()]
    kept: List[str] = []
    unsupported: List[str] = []
    for line in body.splitlines():
        if line.lstrip().startswith("#") or not re.search(r"\w", line):
            kept.append(line.rstrip())
            continue
        marker = _LIST_MARKER.match(line)
        prefix = marker.group(0) if marker else ""
        good: List[str] = []
        for sentence in _sentences(line[len(prefix):]):
            cleaned, cited = _keep_valid(sentence, valid)
            if cited and evidence is not None:
                cited_text = " ".join(evidence.get(int(n), "") for n in re.findall(r"\d+", " ".join(
                    _CITE.findall(cleaned))))
                cited = figures(cleaned) <= figures(cited_text)
            if cited:
                good.append(cleaned)
            else:
                unsupported.append(sentence)
        if good:
            kept.append(prefix + " ".join(good))
    # a heading whose whole section was removed would be an empty promise: drop it
    lines: List[str] = []
    for i, line in enumerate(kept):
        if line.lstrip().startswith("#"):
            following = next((x for x in kept[i + 1:] if x.strip()), "#")
            if following.lstrip().startswith("#"):
                continue
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip(), unsupported


def findings_body(learnings: Sequence[Any]) -> str:
    """One bullet per verified learning, with its quote. No model involved."""
    return "\n".join(f'- {x.claim} [{x.n}] ("{x.quote}")'
                     + (f" (check: {'; '.join(x.flags)})" if getattr(x, "flags", None) else "") for x in learnings)


def sources_section(sources: Sequence[Dict[str, Any]]) -> str:
    rows = [f"{s['n']}. {s['title']} - {s['url']}" for s in sources]
    return "## Sources\n\n" + "\n".join(rows) if rows else ""
