# ================================================================================

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