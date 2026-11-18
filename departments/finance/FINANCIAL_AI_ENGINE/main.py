# ================================================================================

"""Financial AI engine: growth, a straight-line forecast and a threshold health label (plain arithmetic, no model).

compute_growth(previous, current) returns the percent change, or None when previous is zero or negative (growth is
undefined there; 0.0 would read as "no growth"). forecast_linear(data) fits a least-squares line through the values in
order and returns the next point (the value itself for a single item, 0.0 for an empty list). financial_health(revenue,
expenses, debt) scores revenue - expenses - 0.2 * debt and returns "EXCELLENT" (above 50000), "GOOD" (above 10000),
"FAIR" (above 0) or "POOR".
State: keeps none. Failure: no input validation; non-numeric values raise TypeError.
"""
from typing import List, Optional

class FinancialAIEngine:
    """
    Velaris Financial AI Engine
    - Computes growth
    - Forecasts trends (simple linear model)
    - Evaluates financial health scores
    """

    def compute_growth(self, previous: float, current: float) -> Optional[float]:
        """Percent growth, or None when it is undefined (previous is zero or negative): 0.0 would mean "no growth"."""
        if previous <= 0:
            return None
        return ((current - previous) / previous) * 100

    def forecast_linear(self, data: List[float]) -> float:
        if len(data) < 2:
            return data[-1] if data else 0.0
        x = list(range(len(data)))
        y = data
        n = len(data)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(i * i for i in x)
        m = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        b = (sum_y - m * sum_x) / n
        next_x = n
        return m * next_x + b

    def financial_health(self, revenue: float, expenses: float, debt: float) -> str:
        margin = revenue - expenses
        score = margin - (debt * 0.2)
        if score > 50000:
            return "EXCELLENT"
        elif score > 10000:
            return "GOOD"
        elif score > 0:
            return "FAIR"
        return "POOR"

# ================================================================================