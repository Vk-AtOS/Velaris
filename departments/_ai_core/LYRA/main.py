# ================================================================================

"""LYRA: output personality engine that applies a fixed style preset to text.
LyraEngine.set_preset(name) selects one of the built-in presets (neutral, warm, technical) and returns
True, or False for an unknown name. transform(text) returns the text unchanged for neutral, wrapped in
sparkle marks for warm, and prefixed with "[TECH]" and a newline for technical.
This is a simple string stub, not a language model.
State: the active preset is held in memory only (starts as neutral); nothing is persisted.
Failure: set_preset never raises; transform raises TypeError if text is not a string.
"""
class LyraEngine:
    """
    LYRA – Velaris Voice/Output Personality Engine
    Controls:
      - response personality
      - formatting rules
      - emotional tone controls
      - style presets
      - message pipeline
    """

    def __init__(self):
        self.presets = {
            "neutral": {"tone": "neutral", "format": "plain"},
            "warm": {"tone": "warm", "format": "soft"},
            "technical": {"tone": "precise", "format": "structured"},
        }
        self.active_preset = "neutral"

    def set_preset(self, name):
        if name in self.presets:
            self.active_preset = name
            return True
        return False

    def transform(self, text):
        preset = self.presets[self.active_preset]
        tone = preset["tone"]
        fmt = preset["format"]

        if tone == "warm":
            text = "✨ " + text + " ✨"
        if fmt == "structured":
            text = "[TECH]\n" + text

        return text

# ================================================================================