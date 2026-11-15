# ================================================================================

"""Multilingual brain: word-for-word offline translation from registered dictionaries.
MultilingualBrain.register_language(lang, mapping) stores a COPY of a word mapping (keys lower-cased, so
"Hello" and "hello" are one entry; at most 50,000 words) and returns True, or False (keeping the old one) if the
language is already registered; a mapping that is not {text: text} raises ValueError. translate(lang, text) replaces each
word found in the mapping (looked up lower-cased) and keeps spacing and punctuation exactly as written, so "Hello,
world!" becomes "namaste, world!"; unmapped words are kept as written. languages() lists the registered codes. There is
no grammar handling or built-in dictionary.
State: in-memory dict only, nothing persisted, so languages must be registered again after a restart.
Failure: an unregistered language returns the text unchanged; a non-string text raises TypeError.
"""
import re
from typing import Dict

MAX_WORDS = 50_000
_WORD = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")

class MultilingualBrain:
    """
    Velaris Multilingual Brain
    - Provides simple offline translation mappings
    - Registers language dictionaries
    - Performs keyword-level translations
    """

    def __init__(self):
        self.dicts: Dict[str, Dict[str, str]] = {}

    def register_language(self, lang: str, mapping: Dict[str, str]) -> bool:
        if not isinstance(mapping, dict) or len(mapping) > MAX_WORDS or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
            raise ValueError(f"mapping must be {{text: text}} with at most {MAX_WORDS} words")
        if lang in self.dicts:
            return False
        self.dicts[lang] = {k.lower(): v for k, v in mapping.items()}      # a copy: later edits by the caller change nothing
        return True

    def translate(self, lang: str, text: str) -> str:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if lang not in self.dicts:
            return text
        mapping = self.dicts[lang]
        return _WORD.sub(lambda m: mapping.get(m.group(0).lower(), m.group(0)), text)

    def languages(self):
        return list(self.dicts.keys())

# ================================================================================