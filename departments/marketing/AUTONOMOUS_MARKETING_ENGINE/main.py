# ================================================================================

"""Autonomous marketing engine: templated campaign plans and an audience score from measured numbers (no model, no sending).

generate_campaign(product, audience, budget) returns {product, audience, budget, timestamp, strategy}, where strategy
holds three fixed text templates (email, social, landing_page), and appends it to the history; an empty product or
audience, or a budget that is not a finite number of zero or more, raises ValueError. score_audience(audience) takes
{"size": people, "engagement": 0..1, "conversion": 0..1} and returns 0-100 (engagement 50%, conversion 30%, size 20% on
a log scale where a million people is full marks); anything else, including an audience name, raises ValueError.
suggest_channels(score) returns ["social", "video", "influencers"] above 70, ["email", "social"] above 40, otherwise
["email"]. get_history() returns a copy of the campaigns.
State: the history list is in memory only, lost on restart. Nothing is published or sent anywhere.
"""
import math
import time
from typing import Dict, Any, List

from velaris.agentkit.checks import number


class AutonomousMarketingEngine:
    """
    Velaris Autonomous Marketing Engine (AME)
    - Generates marketing campaigns
    - Scores audiences from MEASURED data: {"size": people, "engagement": 0..1, "conversion": 0..1}
    - Produces multi-channel strategy outputs
    - Offline-safe, no external requests
    """

    def __init__(self):
        self.history: List[Dict[str, Any]] = []

    def generate_campaign(self, product: str, audience: str, budget: int) -> Dict[str, Any]:
        if not (isinstance(product, str) and product.strip() and isinstance(audience, str) and audience.strip()):
            raise ValueError("product and audience must be non-empty text")
        if number(budget, 0) is None:
            raise ValueError("budget must be a finite number, zero or more")
        result = {
            "product": product,
            "audience": audience,
            "budget": budget,
            "timestamp": time.time(),
            "strategy": {
                "email": f"Email sequence for {audience}",
                "social": f"Social ads targeting {audience}",
                "landing_page": f"Landing page optimized for {product}",
            }
        }
        self.history.append(result)
        return result

    def score_audience(self, audience: Dict[str, Any]) -> int:
        """0-100: engagement 50%, conversion 30%, size 20% (log scale, a million people is full marks).

        Raises ValueError for anything but measured numbers: a name alone says nothing about an audience."""
        if not isinstance(audience, dict):
            raise ValueError("score_audience needs measured data: {'size', 'engagement', 'conversion'}")
        size, eng, conv = number(audience.get("size"), 0), number(audience.get("engagement"), 0, 1), \
            number(audience.get("conversion"), 0, 1)
        if size is None or eng is None or conv is None:
            raise ValueError("size must be >= 0 and engagement and conversion must be numbers from 0 to 1")
        size_part = min(1.0, math.log10(size + 1) / 6)
        return int(round(100 * (0.5 * eng + 0.3 * conv + 0.2 * size_part)))

    def suggest_channels(self, score: int) -> List[str]:
        if score > 70:
            return ["social", "video", "influencers"]
        elif score > 40:
            return ["email", "social"]
        else:
            return ["email"]

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self.history)

# ================================================================================
