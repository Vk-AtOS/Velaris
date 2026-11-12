"""DOMAIN_REFINER: clean up free-text vertical labels against a canonical list.

CRM records name the same industry many ways ("Health care", "healthcare ",
"Hospitals"). refine() maps each label to one of the caller's canonical verticals:

  exact      the label equals a canonical name, ignoring case and spacing   -> mapped
  alias      the label is in the caller's alias table                       -> mapped
  suggested  a canonical name is a close spelling match (difflib ratio >= cutoff);
             a suggestion is NOT applied, a person confirms it
  unmapped   nothing close enough

Pure string work with the standard library; no model, nothing stored.
"""
import difflib
import logging
from typing import Any, Dict, List, Optional

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("DOMAIN_REFINER")
MAX_LABELS = 20_000


def _norm(label: str) -> str:
    return " ".join(label.lower().split())


class DOMAIN_REFINERAgent:
    def __init__(self):
        self.name = "DOMAIN_REFINER"

    def health_check(self):
        return kit.health("DOMAIN_REFINER")

    def refine(self, labels: Any, canonical: Any, aliases: Optional[Dict[str, str]] = None,
               cutoff: float = 0.85) -> Dict[str, Any]:
        errors: List[str] = []
        if not isinstance(labels, (list, tuple)) or len(labels) > MAX_LABELS \
                or any(not isinstance(x, str) for x in labels):
            errors.append(f"labels must be a list of at most {MAX_LABELS} strings")
        if not isinstance(canonical, (list, tuple)) or any(kit.ident(c, 100) is None for c in canonical):
            errors.append("canonical must be a list of non-empty strings")
        if kit.number(cutoff, 0.5, 1.0) is None:
            errors.append("cutoff must be between 0.5 and 1.0")
        if errors:
            return kit.failed(errors)
        if not canonical:
            return kit.needs_data("no canonical verticals supplied; the refiner does not invent a taxonomy")
        names = {_norm(c): c.strip() for c in canonical}
        alias_map: Dict[str, str] = {}
        if aliases is not None and not isinstance(aliases, dict):
            return kit.failed(["aliases must map a label to one of the canonical verticals"])
        for alias, target in (aliases or {}).items():
            if not isinstance(alias, str) or not isinstance(target, str) or _norm(target) not in names:
                return kit.failed(["aliases must map a label to one of the canonical verticals"])
            alias_map[_norm(alias)] = names[_norm(target)]
        mapping: Dict[str, str] = {}
        suggestions: List[Dict[str, Any]] = []
        unmapped: List[str] = []
        how = {"exact": 0, "alias": 0, "suggested": 0, "unmapped": 0}
        for label in dict.fromkeys(labels):           # distinct labels, first-seen order
            key = _norm(label)
            if key in names:
                mapping[label], kind = names[key], "exact"
            elif key in alias_map:
                mapping[label], kind = alias_map[key], "alias"
            else:
                close = difflib.get_close_matches(key, list(names), n=1, cutoff=cutoff) if key else []
                if close:
                    kind = "suggested"
                    suggestions.append({"label": label, "suggestion": names[close[0]],
                                        "similarity": round(difflib.SequenceMatcher(None, key, close[0]).ratio(), 4)})
                else:
                    kind = "unmapped"
                    unmapped.append(label)
            how[kind] += 1
        return {"status": "ok", "mapping": mapping, "suggestions": suggestions, "unmapped": unmapped,
                "counts": how, "distinct_labels": sum(how.values()),
                "note": "Suggestions are not applied; confirm each, then pass it back as an alias."}
