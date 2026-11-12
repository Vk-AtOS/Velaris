"""GSTIN structure and check character.

Layout (15 characters): 2-digit State code, the holder's 10-character PAN, a 1-character entity
number (1-9 or A-Z), the letter Z, and a check character. The check character is computed over
the first 14 characters in base 36 (digits then A-Z): each value is multiplied by 1 at odd
positions and 2 at even positions (counting from 1), each product p adds p // 36 + p % 36, and
the check value is (36 - sum % 36) % 36.

ponytail: layout and algorithm are the portal's long-standing public format, written here from
that description; this registry did not read the GSTN specification. The State code is only
checked to be 01-99; the list of valid codes was not read.
"""
import re
from typing import Any, Dict

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_FORMAT = re.compile(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]")


def check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        product = ALPHABET.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return ALPHABET[(36 - total % 36) % 36]


def validate_gstin(value: Any) -> Dict[str, Any]:
    """{valid, reason, state_code, pan}. Never raises."""
    g = value.strip().upper() if isinstance(value, str) else ""
    if len(g) != 15 or not _FORMAT.fullmatch(g):
        return {"valid": False, "reason": "not in the 15-character GSTIN format", "state_code": None, "pan": None}
    if g[:2] == "00":
        return {"valid": False, "reason": "State code 00 does not exist", "state_code": None, "pan": None}
    if check_char(g[:14]) != g[14]:
        return {"valid": False, "reason": "check character does not match", "state_code": g[:2], "pan": g[2:12]}
    return {"valid": True, "reason": "", "state_code": g[:2], "pan": g[2:12]}
