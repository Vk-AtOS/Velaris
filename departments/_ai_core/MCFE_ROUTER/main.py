"""MCFE_ROUTER: which department handles a subject domain.

route(domain) looks the domain up in a fixed table and confirms that the
department exists under departments/. A domain with no department here
(medical) or an unknown domain is "unrouted": it goes to a person, not to a
default department.
"""
from typing import Any, Dict, Optional

from velaris.agentkit.results import health
from velaris.agents import department_dirs

NAME = "MCFE_ROUTER"
DEPARTMENT: Dict[str, Optional[str]] = {
    "finance": "finance", "legal": "legal_compliance", "engineering": "it_infrastructure",
    "governance": "executive", "business": "operations", "psychology": "hr", "science": "data_knowledge",
    "medical": None,
}


class MCFERouterAgent:
    def health_check(self):
        return health(NAME)

    def route(self, domain: Any) -> Dict[str, Any]:
        """Returns route "ok" with the department, or route "unrouted" with the reason."""
        base = {"route": "unrouted", "domain": domain, "department": None}
        if not isinstance(domain, str) or domain not in DEPARTMENT:
            return {**base, "status": "unknown_domain", "reason": f"no routing rule for domain {domain!r}"}
        department = DEPARTMENT[domain]
        if department is None:
            return {**base, "status": "unrouted", "reason": f"no department handles {domain!r}; needs a person"}
        if department not in {d.name for d in department_dirs()}:
            return {**base, "status": "unrouted", "reason": f"department {department!r} does not exist"}
        return {"route": "ok", "status": "ok", "domain": domain, "department": department}
