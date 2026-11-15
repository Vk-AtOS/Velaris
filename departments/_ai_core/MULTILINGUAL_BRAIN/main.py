# ================================================================================

"""Multilingual brain: word-for-word offline translation from registered dictionaries.
MultilingualBrain.register_language(lang, mapping) stores a word mapping and returns True, or False
(keeping the old one) if the language is already registered. translate(lang, text) splits on
whitespace and replaces each lowercased word found in the mapping; unmapped words are kept as written.
languages() lists the registered codes. There is no grammar handling or built-in dictionary.
State: in-memory dict only, nothing persisted, so languages must be registered again after a restart.
Failure: an unregistered language returns the text unchanged; a non-string text raises AttributeError.
"""
from typing import Dict

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
        if lang in self.dicts:
            return False
        self.dicts[lang] = mapping
        return True

    def translate(self, lang: str, text: str) -> str:
        if lang not in self.dicts:
            return text
        mapping = self.dicts[lang]
        words = text.split()
        out = []
        for w in words:
            out.append(mapping.get(w.lower(), w))
        return " ".join(out)

    def languages(self):
        return list(self.dicts.keys())

# ================================================================================