import logging
import os
from typing import Dict, Any

from velaris.agents.ZOHO_CONNECTOR.main import ZohoConnector

logger = logging.getLogger("ZOHO_PAYROLL")


class ZohoPayrollConnector:
    """
    Pulls payroll data from Zoho Payroll (India):
    - Payslips per employee per month
    - Salary components (basic, HRA, special allowance)
    - Statutory deductions (EPF, ESI, TDS, PT)
    - Net pay and YTD summaries
    """
    BASE = "https://payroll.zoho.in/api/v1"

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.zoho = ZohoConnector(config)
        self.org_id = config.get("org_id") or os.getenv("ZOHO_ORG_ID", "")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "ZOHO_PAYROLL", "status": "ok"}

    def get_payslip(self, employee_id: str, year: int, month: int) -> Dict:
        """Returns full payslip breakdown for a given month."""
        resp = self.zoho.get(
            f"{self.BASE}/payslips",
            {"employee_id": employee_id, "year": year, "month": month}
        )
        return resp.get("payslip", {})

    def get_ytd_summary(self, employee_id: str, financial_year: int) -> Dict:
        """
        Returns year-to-date earnings, deductions, and net pay.
        financial_year: e.g. 2026 means Apr 2025 - Mar 2026
        """
        resp = self.zoho.get(
            f"{self.BASE}/employees/{employee_id}/ytd",
            {"financial_year": financial_year}
        )
        return resp.get("ytd_summary", {})

    def get_statutory_deductions(self, employee_id: str, year: int, month: int) -> Dict:
        """Returns EPF, ESI, TDS, Professional Tax for the month."""
        payslip = self.get_payslip(employee_id, year, month)
        deductions = payslip.get("deductions", [])
        statutory = {}
        for d in deductions:
            name = d.get("name", "").upper()
            if any(k in name for k in ["EPF", "PF", "ESI", "TDS", "PROFESSIONAL TAX", "PT"]):
                statutory[d["name"]] = d.get("amount", 0)
        return {"employee_id": employee_id, "year": year, "month": month, "statutory": statutory}

    def get_cost_to_company(self, employee_id: str, year: int, month: int) -> float:
        """Returns total CTC including employer contributions."""
        payslip = self.get_payslip(employee_id, year, month)
        return payslip.get("cost_to_company", 0)
