# ================================================================================

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
            text = "[TECH]/n" + text

        return text

# ================================================================================