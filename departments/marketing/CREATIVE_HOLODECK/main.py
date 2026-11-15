# ================================================================================

"""Creative holodeck: composes a text scene description from fixed style, mood, element and action lists; rule-based, not a generative model.

CreativeHolodeck: compose(style, mood, element, action) validates each against its list
(styles fantasy/scifi/noir/minimal, moods bright/dark/calm/chaotic, elements
forest/city/ocean/desert, actions exploring/resting/battling/searching) and returns the
four values plus a description sentence; random_scene() composes a random valid choice.
State: keeps no state beyond the fixed lists; random_scene is not seeded.
Failure: an unknown value returns {"error": "invalid_style" | "invalid_mood" |
"invalid_element" | "invalid_action"} (checked in that order).
"""

from typing import List, Dict


class CreativeHolodeck:
    """
    Velaris Creative Holodeck
    - Generates simple offline creative scenes
    - Mixes elements, styles, moods, and actions
    - Not a generative model — rule-based composition only
    """

    def __init__(self):
        self.styles = ["fantasy", "scifi", "noir", "minimal"]
        self.moods = ["bright", "dark", "calm", "chaotic"]
        self.elements = ["forest", "city", "ocean", "desert"]
        self.actions = ["exploring", "resting", "battling", "searching"]

    def compose(self, style: str, mood: str, element: str, action: str) -> Dict[str, str]:
        """Creates a combined creative scene description."""
        if style not in self.styles:
            return {"error": "invalid_style"}
        if mood not in self.moods:
            return {"error": "invalid_mood"}
        if element not in self.elements:
            return {"error": "invalid_element"}
        if action not in self.actions:
            return {"error": "invalid_action"}

        description = f"A {mood} {style} scene set in a {element}, where characters are {action}."
        return {
            "style": style,
            "mood": mood,
            "element": element,
            "action": action,
            "description": description
        }

    def random_scene(self) -> Dict[str, str]:
        """Quick random preset scene."""
        import random
        return self.compose(
            random.choice(self.styles),
            random.choice(self.moods),
            random.choice(self.elements),
            random.choice(self.actions)
        )

# ================================================================================