# ================================================================================

"""Autonomous sales navigator: weighted lead scoring (fixed formula, no learning).

add_lead(name, budget, interest, fit) stores a lead; score_lead(lead) is int(0.4*budget +
0.3*interest + 0.3*fit); predict_close_probability(lead) is score/100 capped at 1.0 (not a
trained probability); suggest_strategy(lead) returns one of three fixed texts for score >80,
>50 and lower; top_leads(n) returns the n best leads. State: leads list in memory only, lost
on restart. A lead missing budget, interest or fit raises KeyError.
"""
from typing import Dict, Any, List

class AutonomousSalesNavigator:
    """
    Velaris Autonomous Sales Navigator
    - Scores leads
    - Predicts deal likelihood
    - Suggests outreach strategies
    """

    def __init__(self):
        self.leads: List[Dict[str, Any]] = []

    def add_lead(self, name: str, budget: int, interest: int, fit: int) -> Dict[str, Any]:
        lead = {
            "name": name,
            "budget": budget,
            "interest": interest,
            "fit": fit,
        }
        self.leads.append(lead)
        return lead

    def score_lead(self, lead: Dict[str, Any]) -> int:
        return int(
            (lead["budget"] * 0.4) +
            (lead["interest"] * 0.3) +
            (lead["fit"] * 0.3)
        )

    def predict_close_probability(self, lead: Dict[str, Any]) -> float:
        score = self.score_lead(lead)
        return min(1.0, score / 100)

    def suggest_strategy(self, lead: Dict[str, Any]) -> str:
        score = self.score_lead(lead)
        if score > 80:
            return "High-touch call and proposal"
        elif score > 50:
            return "Email sequence + call"
        return "Nurture with periodic content"

    def top_leads(self, n: int) -> List[Dict[str, Any]]:
        sorted_leads = sorted(self.leads, key=lambda l: self.score_lead(l), reverse=True)
        return sorted_leads[:n]

# ================================================================================