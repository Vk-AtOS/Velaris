"""Cohortus: assigns team roles and splits members into clusters.
CohortusAgent.assign_roles(members, roles) maps each member to a role in order, repeating the roles
cyclically; with no roles every member maps to None. collaboration_clusters(members, cluster_size=2)
returns consecutive chunks of that size, the last possibly smaller. Order-based, not skill-based.
State: keeps none. Failure: a cluster_size of 0 raises ValueError and a negative size returns odd
slices; there is no other validation.
"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger("COHORTUS")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - COHORTUS - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class CohortusAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "COHORTUS", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def assign_roles(self, members: List[str], roles: List[str]) -> Dict[str, str]:
        """
        Assigns roles to members in order.
        If roles < members, repeat roles cyclically.
        """
        logger.debug("Assigning roles members=%s roles=%s", members, roles)
        if not roles:
            return {m: None for m in members}

        assigned = {}
        for i, m in enumerate(members):
            assigned[m] = roles[i % len(roles)]
        logger.debug("Assigned roles: %s", assigned)
        return assigned

    def collaboration_clusters(self, members: List[str], cluster_size: int = 2) -> List[List[str]]:
        """
        Splits members into clusters of fixed size.
        Example: members=[A,B,C,D,E], size=2 -> [[A,B],[C,D],[E]]
        """
        logger.debug("Clustering members=%s size=%s", members, cluster_size)
        clusters = []
        for i in range(0, len(members), cluster_size):
            clusters.append(members[i:i+cluster_size])
        logger.debug("Clusters: %s", clusters)
        return clusters
