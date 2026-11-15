import logging
import os
import re
from typing import Dict, Any, Optional

from velaris.agents.ZOHO_CONNECTOR.main import ZohoConnector
from velaris.core.access import Caller, authorize_read

logger = logging.getLogger("ZOHO_PAYROLL")


# Whole words only: "PT" must not match "OPTIONAL BONUS" or "PF" "SPF REFUND"; a deduction is statutory by its name.
_STATUTORY = re.compile(r"(?<![A-Z])(EPF|PF|ESI|TDS|PT|PROFESSIONAL TAX)(?![A-Z])")


class ZohoPayrollConnector:
    """
    Pulls payroll data from Zoho Payroll (India):
    - Payslips per employee per month
    - Salary components (basic, HRA, special allowance)
    - Statutory deductions (EPF, ESI, TDS, PT)
    - Net pay and YTD summaries

    Every method returns one employee's pay, so each one first asks velaris.core.access
    whether the caller (passed as `caller=`, or set with acting_as) may read it: the
    employee themself, or a payroll or HR administrator. Anyone else, or no caller at
    all, gets AccessDenied, and the decision is written to the trace either way.
    """
    BASE = "https://payroll.zoho.in/api/v1"

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.zoho = ZohoConnector(self.config)
        self.org_id = self.config.get("org_id") or os.getenv("ZOHO_ORG_ID", "")
        self.org = self.config.get("org")      # Velaris organisation this payroll belongs to; None = single org

    def health_check(self) -> Dict[str, Any]:
        configured = self.zoho.health_check()["configured"]
        return {"agent": "ZOHO_PAYROLL", "status": "ok" if configured else "unconfigured", "configured": configured}

    def _allow(self, employee_id: str, caller: Optional[Caller]) -> None:
        authorize_read("pay", employee_id, agent="ZOHO_PAYROLL", caller=caller, org=self.org)

    def get_payslip(self, employee_id: str, year: int, month: int, *, caller: Optional[Caller] = None) -> Dict:
        """Returns full payslip breakdown for a given month."""
        self._allow(employee_id, caller)
        return self._payslip(employee_id, year, month)

    def _payslip(self, employee_id: str, year: int, month: int) -> Dict:
        resp = self.zoho.get(
            f"{self.BASE}/payslips",
            {"employee_id": employee_id, "year": year, "month": month}
        )
        return resp.get("payslip", {})

    def get_ytd_summary(self, employee_id: str, financial_year: int, *, caller: Optional[Caller] = None) -> Dict:
        """
        Returns year-to-date earnings, deductions, and net pay.
        financial_year: e.g. 2026 means Apr 2025 - Mar 2026
        """
        self._allow(employee_id, caller)
        resp = self.zoho.get(
            f"{self.BASE}/employees/{employee_id}/ytd",
            {"financial_year": financial_year}
        )
        return resp.get("ytd_summary", {})

    def get_statutory_deductions(self, employee_id: str, year: int, month: int, *,
                                 caller: Optional[Caller] = None) -> Dict:
        """Returns EPF, ESI, TDS, Professional Tax for the month."""
        self._allow(employee_id, caller)
        payslip = self._payslip(employee_id, year, month)
        deductions = payslip.get("deductions", [])
        statutory = {}
        for d in deductions:
            name = d.get("name", "").upper()
            if _STATUTORY.search(name):
                statutory[d["name"]] = d.get("amount", 0)
        return {"employee_id": employee_id, "year": year, "month": month, "statutory": statutory}

    def get_cost_to_company(self, employee_id: str, year: int, month: int, *,
                            caller: Optional[Caller] = None) -> float:
        """Returns total CTC including employer contributions."""
        self._allow(employee_id, caller)
        payslip = self._payslip(employee_id, year, month)
        return payslip.get("cost_to_company", 0)
