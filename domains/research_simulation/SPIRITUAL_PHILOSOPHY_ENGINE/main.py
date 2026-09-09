# ================================================================================

from typing import Dict, List


class SpiritualPhilosophyEngine:
    """
    Velaris Spiritual / Philosophy Engine (Offline, Non-doctrinal)
    - Stores neutral philosophical concepts
    - Allows retrieval by theme
    - Supports reflective prompts in a safe, abstract manner
    """

    def __init__(self):
        self.themes: Dict[str, List[str]] = {}

    def add_concept(self, theme: str, concept: str) -> bool:
        key = theme.lower()
        if key not in self.themes:
            self.themes[key] = []
        if concept in self.themes[key]:
            return False
        self.themes[key].append(concept)
        return True

    def list_themes(self) -> List[str]:
        return list(self.themes.keys())

    def concepts_in(self, theme: str) -> List[str]:
        return self.themes.get(theme.lower(), [])

    def reflect(self, theme: str) -> str:
        """
        Produces a neutral reflection sentence based on stored concepts.
        """
        concepts = self.concepts_in(theme)
        if not concepts:
            return "No concepts available to reflect on."
        joined = ", ".join(concepts)
        return f"Reflection on {theme}: Consider the ideas of {joined}."

# ================================================================================