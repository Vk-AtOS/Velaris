"""Report checking for the research pipeline: the part that is code, not model.

The model drafts the answer; this module decides what survives:

  verify_report()    every sentence or bullet that says something must carry a
                     citation [n] whose number is in the registry. Unknown
                     numbers are deleted; a sentence left with no citation is
                     cut from the body and returned in `unsupported`.
  findings_body()    the answer built without a model: one bullet per verified
                     learning. Used when the model's draft is missing or empty
                     after checking.
  sources_section()  the numbered source list, generated from the registry so
                     a model can never invent or renumber a source.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Set, Tuple

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


def verify_report(body: str, valid: Set[int]) -> Tuple[str, List[str]]:
    """Keep only cited statements. Returns (checked body, sentences that were removed).

    Headings and lines with no words pass through; they are layout. Everything
    else is split into sentences and each one needs a citation of its own.
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
    return "\n".join(f'- {x.claim} [{x.n}] ("{x.quote}")' for x in learnings)


def sources_section(sources: Sequence[Dict[str, Any]]) -> str:
    rows = [f"{s['n']}. {s['title']} - {s['url']}" for s in sources]
    return "## Sources\n\n" + "\n".join(rows) if rows else ""
