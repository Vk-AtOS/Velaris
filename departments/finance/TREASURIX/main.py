import logging
from typing import Dict, Any, List

logger = logging.getLogger("TREASURIX")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - TREASURIX - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class TreasurixAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.reserves = self.config.get("initial_reserves", 0.0)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self) -> Dict[str, Any]:
        status = {"agent": "TREASURIX", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def project_cashflow(self, inflows: List[float], outflows: List[float]) -> float:
        """
        Project net cashflow over the provided periods.
        inflows/outflows lists should be same length; returns net sum over all periods.
        """
        if len(inflows) != len(outflows):
            raise ValueError("inflows and outflows must have same length")
        net = sum(inflows) - sum(outflows)
        logger.debug("Projected cashflow net=%s inflows=%s outflows=%s", net, inflows, outflows)
        return net

    def runway_months(self, monthly_burn: float, reserves: float = None) -> float:
        """
        Compute runway in months given monthly burn and current reserves.
        If monthly_burn <= 0, returns float('inf') to indicate non-burning.
        """
        r = reserves if reserves is not None else self.reserves
        if monthly_burn <= 0:
            logger.debug("Monthly burn <= 0, runway infinite")
            return float("inf")
        months = r / monthly_burn
        logger.debug("Runway months=%s reserves=%s monthly_burn=%s", months, r, monthly_burn)
        return months

    def reserve_ratio(self, liquid_assets: float, short_term_liabilities: float) -> float:
        """
        Simple reserve ratio = liquid_assets / short_term_liabilities
        If liabilities == 0, return float('inf').
        """
        if short_term_liabilities == 0:
            logger.debug("Short-term liabilities zero, reserve ratio infinite")
            return float("inf")
        ratio = liquid_assets / short_term_liabilities
        logger.debug("Reserve ratio=%s assets=%s liabilities=%s", ratio, liquid_assets, short_term_liabilities)
        return ratio
