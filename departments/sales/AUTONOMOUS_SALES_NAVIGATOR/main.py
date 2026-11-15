# ================================================================================

from typing import Dict, Any, List

from velaris.agentkit.checks import number


def _score_field(lead: Dict[str, Any], key: str) -> float:
    v = number(lead.get(key) if isinstance(lead, dict) else None, 0, 100)
    if v is None:
        raise ValueError(f"{key} must be a number from 0 to 100")
    return v


class AutonomousSalesNavigator:
    """
    Velaris Autonomous Sales Navigator
    - Scores leads from three 0-100 ratings (budget 40%, interest 30%, fit 30%)
    - close ratio = score / 100. It is a RATIO of the weighted ratings, NOT a probability: nothing here is
      calibrated against won/lost history, so do not read 0.7 as "70% will close"
    - Suggests outreach strategies
    """

    def __init__(self):
        self.leads: List[Dict[str, Any]] = []

    def add_lead(self, name: str, budget: int, interest: int, fit: int) -> Dict[str, Any]:
        """Raises ValueError for a missing name or a rating that is not a finite number from 0 to 100."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be non-empty text")
        lead = {"name": name, "budget": budget, "interest": interest, "fit": fit}
        self.score_lead(lead)                      # validates all three ratings
        self.leads.append(lead)
        return lead

    def score_lead(self, lead: Dict[str, Any]) -> int:
        return int(_score_field(lead, "budget") * 0.4 + _score_field(lead, "interest") * 0.3
                   + _score_field(lead, "fit") * 0.3)

    def predict_close_probability(self, lead: Dict[str, Any]) -> float:
        """The close ratio (score / 100), uncalibrated; see the class docstring."""
        return min(1.0, self.score_lead(lead) / 100)

    def suggest_strategy(self, lead: Dict[str, Any]) -> str:
        score = self.score_lead(lead)
        if score > 80:
            return "High-touch call and proposal"
        elif score > 50:
            return "Email sequence + call"
        return "Nurture with periodic content"

    def top_leads(self, n: int) -> List[Dict[str, Any]]:
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError("n must be a whole number, zero or more")
        sorted_leads = sorted(self.leads, key=lambda l: self.score_lead(l), reverse=True)
        return sorted_leads[:n]

# ================================================================================
