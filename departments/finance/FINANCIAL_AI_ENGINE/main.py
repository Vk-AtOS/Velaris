# ================================================================================

from typing import List

class FinancialAIEngine:
    """
    Velaris Financial AI Engine
    - Computes growth
    - Forecasts trends (simple linear model)
    - Evaluates financial health scores
    """

    def compute_growth(self, previous: float, current: float) -> float:
        if previous <= 0:
            return 0.0
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