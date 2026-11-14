"""MPC_PREPROC: cleans raw records so that records from different sources can be compared.

MPC is read here as "multi-source processing": MPC_PREPROC cleans each
source's record, MPC_FUSION merges them, MPC_CORE runs both.

Per record: keys become snake_case, text is unicode-normalised and
whitespace-collapsed, empty values are dropped, numeric text ("1,200.50")
becomes a number, dd/mm/yyyy dates become yyyy-mm-dd. With redact=True
secrets and personal identifiers in text are masked (velaris.intel.guard).
In a list, exact duplicates (after cleaning) are removed. Every change is counted.
ponytail: dd/mm/yyyy is assumed (Indian convention); a US-format source needs a flag.
"""
import json
import re
from typing import Any, Dict, List, Tuple

from velaris.agentkit.results import health, invalid
from velaris.intel import guard

NAME = "MPC_PREPROC"
MAX_RECORDS = 10_000
# Comma-grouped, or a plain integer of at most 9 digits with no leading zero; optional decimals.
# Longer or zero-led digit runs are identifiers (phone numbers, PIN codes, account numbers) and stay text.
_NUMERIC = re.compile(r"^[+-]?(?:[1-9]\d{0,2}(?:,\d{2,3})+|0|[1-9]\d{0,8})(?:\.\d+)?$")
_DMY = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_KEY = re.compile(r"[^a-z0-9]+")


def _key(key: Any) -> str:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(key))
    return _KEY.sub("_", spaced.lower()).strip("_")


def _value(value: Any, redact: bool, stats: Dict[str, int]) -> Any:
    if isinstance(value, dict):
        return _record(value, redact, stats)
    if isinstance(value, list):
        return [v for v in (_value(x, redact, stats) for x in value) if v not in (None, "", {}, [])]
    if not isinstance(value, str):
        return value
    text = " ".join(guard.normalise(value).split())
    if redact:                  # mask first: a number-shaped identifier must not be parsed away before redaction sees it
        masked, counts = guard.redact(text)
        if counts:
            stats["values_redacted"] += sum(counts.values())
            text = masked
    if _NUMERIC.match(text):
        stats["numbers_parsed"] += 1
        return float(text.replace(",", ""))
    m = _DMY.match(text)
    if m and 1 <= int(m.group(1)) <= 31 and 1 <= int(m.group(2)) <= 12:
        stats["dates_normalised"] += 1
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    if text != value:
        stats["text_cleaned"] += 1
    return text


def _record(record: Dict[str, Any], redact: bool, stats: Dict[str, int]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in record.items():
        cleaned = _value(value, redact, stats)
        name = _key(key)
        if cleaned in (None, "", {}, []) or not name:
            stats["empty_dropped"] += 1
            continue
        if name != key:
            stats["keys_renamed"] += 1
        out[name] = cleaned
    return out


class MPC_PREPROCAgent:
    def health_check(self):
        return health(NAME)

    def preprocess(self, records: Any, redact: bool = False) -> Dict[str, Any]:
        """Clean one record (a dict) or a list of records. Returns records, record (the first) and stats."""
        many = records if isinstance(records, list) else [records]
        if not many or len(many) > MAX_RECORDS or not all(isinstance(r, dict) for r in many):
            return invalid(f"expected a record or a list of 1..{MAX_RECORDS} records (objects)", records=[])
        stats = {k: 0 for k in ("keys_renamed", "text_cleaned", "numbers_parsed", "dates_normalised",
                                "values_redacted", "empty_dropped", "duplicates_removed")}
        seen, cleaned = set(), []
        for record in many:
            row = _record(record, bool(redact), stats)
            fingerprint = json.dumps(row, sort_keys=True, default=str)
            if fingerprint in seen:
                stats["duplicates_removed"] += 1
                continue
            seen.add(fingerprint)
            cleaned.append(row)
        return {"status": "ok", "records": cleaned, "record": cleaned[0], "stats": stats}
