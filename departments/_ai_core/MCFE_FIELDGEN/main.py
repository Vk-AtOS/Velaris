"""MCFE_FIELDGEN: the fields a record of a given domain needs, and their values found in a text.

generate_field(domain) returns the field list for that domain (name, type,
required). extract(text, domain) fills those fields from the text using typed
patterns only (amounts with a currency mark, yyyy-mm-dd or dd/mm/yyyy dates,
e-mail addresses, percentages, references such as INV-204): the first value of
each kind is taken. Required fields that could not be found are listed in
"missing"; nothing is invented to fill them.
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit import aicore_b_text as textkit
from velaris.agentkit.aicore_b_common import fail, health, invalid, text as as_text

NAME = "MCFE_FIELDGEN"


def _f(name: str, kind: str, required: bool = False) -> Dict[str, Any]:
    return {"name": name, "type": kind, "required": required}


_SUMMARY = _f("summary", "text", True)
FIELDS: Dict[str, List[Dict[str, Any]]] = {
    "finance": [_SUMMARY, _f("amount", "amount", True), _f("due_date", "date"), _f("reference", "reference"),
                _f("contact_email", "email")],
    "legal": [_SUMMARY, _f("reference", "reference", True), _f("effective_date", "date"), _f("amount", "amount"),
              _f("contact_email", "email")],
    "engineering": [_SUMMARY, _f("reference", "reference"), _f("date", "date"), _f("contact_email", "email")],
    "business": [_SUMMARY, _f("contact_email", "email"), _f("amount", "amount"), _f("date", "date"),
                 _f("reference", "reference")],
    "governance": [_SUMMARY, _f("reference", "reference"), _f("date", "date")],
    "medical": [_SUMMARY, _f("date", "date"), _f("reference", "reference")],
    "science": [_SUMMARY, _f("date", "date"), _f("percentage", "percentage"), _f("reference", "reference")],
    "psychology": [_SUMMARY, _f("date", "date"), _f("contact_email", "email")],
}
_SOURCE = {"amount": "amounts", "date": "dates", "email": "emails", "percentage": "percentages",
           "reference": "references"}
SUMMARY_CHARS = 280


class MCFEFieldGenAgent:
    def health_check(self):
        return health(NAME)

    def generate_field(self, domain: Any) -> Dict[str, Any]:
        """The field list for a domain. "field" is "generated" on success, None otherwise."""
        if not isinstance(domain, str) or domain not in FIELDS:
            return {"field": None, "domain": domain, "fields": [],
                    **fail("unknown_domain", f"no field list for domain {domain!r}")}
        return {"status": "ok", "field": "generated", "domain": domain, "fields": [dict(f) for f in FIELDS[domain]]}

    def extract(self, text: Any, domain: Any) -> Dict[str, Any]:
        """Fill the domain's fields from the text. Returns record, missing (required, not found)."""
        body = as_text(text)
        schema: Optional[Dict[str, Any]] = self.generate_field(domain)
        if body is None:
            return invalid("text must be a non-empty string", record={}, missing=[])
        if schema["status"] != "ok":
            return {**schema, "record": {}, "missing": []}
        cleaned = textkit.clean(body)
        found = textkit.entities(cleaned)
        record: Dict[str, Any] = {}
        for field in schema["fields"]:
            if field["type"] == "text":
                record[field["name"]] = cleaned[:SUMMARY_CHARS]
            elif found[_SOURCE[field["type"]]]:
                record[field["name"]] = found[_SOURCE[field["type"]]][0]
        missing = [f["name"] for f in schema["fields"] if f["required"] and f["name"] not in record]
        return {"status": "ok" if not missing else "incomplete", "domain": domain, "record": record,
                "missing": missing}
