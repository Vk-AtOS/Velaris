import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
from typing import Dict, Any, List, Optional
from velaris.agents.ZOHO_PAYROLL.main import ZohoPayrollConnector

logger = logging.getLogger("PAYROLL_ENGINE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - PAYROLL_ENGINE - %(levelname)s - %(message)s"))
logger.addHandler(handler)

# India statutory rates (FY 2025-26)
_EPF_EMPLOYEE_RATE = 0.12        # 12% of basic
_EPF_EMPLOYER_RATE = 0.12
_ESI_EMPLOYEE_RATE = 0.0075      # 0.75% of gross (if gross <= 21000/mo)
_ESI_EMPLOYER_RATE = 0.0325
_ESI_CEILING_GROSS = 21000
_PT_SLABS = [                    # Professional Tax (Karnataka/TN typical)
    (10000, 0),
    (15000, 150),
    (999999, 200),
]


def _compute_pt(gross: float) -> float:
    for ceiling, tax in _PT_SLABS:
        if gross <= ceiling:
            return float(tax)
    return 200.0


def _compute_statutory(basic: float, gross: float) -> Dict[str, float]:
    epf_emp = round(basic * _EPF_EMPLOYEE_RATE, 2)
    epf_er = round(basic * _EPF_EMPLOYER_RATE, 2)
    esi_eligible = gross <= _ESI_CEILING_GROSS
    esi_emp = round(gross * _ESI_EMPLOYEE_RATE, 2) if esi_eligible else 0.0
    esi_er = round(gross * _ESI_EMPLOYER_RATE, 2) if esi_eligible else 0.0
    pt = _compute_pt(gross)
    return {
        "epf_employee": epf_emp,
        "epf_employer": epf_er,
        "esi_employee": esi_emp,
        "esi_employer": esi_er,
        "professional_tax": pt,
        "total_employee_deductions": round(epf_emp + esi_emp + pt, 2),
        "total_employer_contributions": round(epf_er + esi_er, 2),
    }


class PayrollEngine:
    """
    India statutory payroll computation engine.
    Wraps Zoho Payroll for live data; also does local computation
    from raw salary components when Zoho credentials are unavailable.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._zoho: Optional[ZohoPayrollConnector] = None
        if config and config.get("zoho_enabled"):
            self._zoho = ZohoPayrollConnector(config)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "PAYROLL_ENGINE", "status": "ok", "zoho_enabled": self._zoho is not None}

    # ── Local computation (no Zoho creds needed) ──────────────────────────
    def compute(self, employee_id: str, basic: float, hra: float,
                special_allowance: float, tds: float = 0.0) -> Dict[str, Any]:
        """
        Compute monthly take-home from salary components.
        basic, hra, special_allowance, tds — all monthly INR values.
        """
        gross = basic + hra + special_allowance
        statutory = _compute_statutory(basic, gross)
        total_deductions = round(statutory["total_employee_deductions"] + tds, 2)
        net_pay = round(gross - total_deductions, 2)
        ctc = round(gross + statutory["total_employer_contributions"], 2)

        logger.debug("Payroll computed for %s: gross=%.2f net=%.2f", employee_id, gross, net_pay)
        return {
            "employee_id": employee_id,
            "gross": gross,
            "components": {"basic": basic, "hra": hra, "special_allowance": special_allowance},
            "statutory": statutory,
            "tds": tds,
            "total_deductions": total_deductions,
            "net_pay": net_pay,
            "ctc_monthly": ctc,
            "ctc_annual": round(ctc * 12, 2),
        }

    def compute_bulk(self, employees: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        employees: [{"employee_id": ..., "basic": ..., "hra": ..., "special_allowance": ..., "tds": ...}]
        """
        return [self.compute(**e) for e in employees]

    def org_statutory_summary(self, employees: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregates EPF/ESI/PT obligations across the org for one month.
        """
        results = self.compute_bulk(employees)
        totals: Dict[str, float] = {
            "total_epf_employee": 0.0, "total_epf_employer": 0.0,
            "total_esi_employee": 0.0, "total_esi_employer": 0.0,
            "total_pt": 0.0, "total_tds": 0.0,
            "total_gross": 0.0, "total_net_pay": 0.0,
        }
        for r in results:
            s = r["statutory"]
            totals["total_epf_employee"] += s["epf_employee"]
            totals["total_epf_employer"] += s["epf_employer"]
            totals["total_esi_employee"] += s["esi_employee"]
            totals["total_esi_employer"] += s["esi_employer"]
            totals["total_pt"] += s["professional_tax"]
            totals["total_tds"] += r.get("tds", 0)
            totals["total_gross"] += r["gross"]
            totals["total_net_pay"] += r["net_pay"]
        totals = {k: round(v, 2) for k, v in totals.items()}
        totals["headcount"] = len(results)
        totals["total_compliance_liability"] = round(
            totals["total_epf_employee"] + totals["total_epf_employer"] +
            totals["total_esi_employee"] + totals["total_esi_employer"] +
            totals["total_pt"], 2
        )
        return totals

    # ── Zoho-backed methods (requires zoho_enabled=True) ──────────────────
    def get_payslip(self, employee_id: str, year: int, month: int) -> Dict:
        if not self._zoho:
            return {"error": "zoho_not_configured"}
        return self._zoho.get_payslip(employee_id, year, month)

    def get_statutory_deductions(self, employee_id: str, year: int, month: int) -> Dict:
        if not self._zoho:
            return {"error": "zoho_not_configured"}
        return self._zoho.get_statutory_deductions(employee_id, year, month)

    def get_ytd_summary(self, employee_id: str, financial_year: int) -> Dict:
        if not self._zoho:
            return {"error": "zoho_not_configured"}
        return self._zoho.get_ytd_summary(employee_id, financial_year)


if __name__ == "__main__":
    eng = PayrollEngine()
    result = eng.compute("EMP001", basic=40000, hra=16000, special_allowance=14000, tds=3500)
    print("Net pay:", result["net_pay"])
    print("CTC annual:", result["ctc_annual"])
    print("Statutory:", result["statutory"])
    org = eng.org_statutory_summary([
        {"employee_id": "E1", "basic": 40000, "hra": 16000, "special_allowance": 14000},
        {"employee_id": "E2", "basic": 25000, "hra": 10000, "special_allowance": 5000},
    ])
    print("Org EPF liability:", org["total_epf_employer"])
