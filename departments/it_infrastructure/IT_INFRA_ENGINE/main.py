"""IT_INFRA_ENGINE: validate an infrastructure request, plan it, and judge reported VM health.

No cloud account is attached to this agent, so provision() creates nothing. It
checks the request and stores a deterministic plan: VM names, one address per
VM taken in order from the network's usable hosts, and the totals implied by
VM_SIZES (a sizing table declared here, not a provider's catalogue). The result
says "planned" - the plan is what an operator or a provider integration applies.

health_check(infra_id, vms) compares what the caller reports about the VMs with
the stored plan:

    healthy    every planned VM is reported and running
    degraded   at least one, but not all, planned VMs are running
    down       none are running

health_check() with no arguments is the agent's own liveness answer.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from velaris.agentkit.checks import is_name
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState

NAME = "IT_INFRA_ENGINE"
VM_SIZES = {"small": {"vcpu": 1, "mem_gb": 2}, "medium": {"vcpu": 2, "mem_gb": 8},
            "large": {"vcpu": 8, "mem_gb": 32}, "gpu-1": {"vcpu": 8, "mem_gb": 64}}


@dataclass
class InfraConfig:
    name: str
    region: str
    vm_count: int
    vm_type: str
    network_cidr: str
    tags: Dict[str, str]


class ITInfraEngine:
    SUPPORTED_REGIONS = {"us-east-1", "us-west-2", "eu-central-1", "ap-south-1"}
    SUPPORTED_VM_TYPES = set(VM_SIZES)
    MIN_VMS = 1
    MAX_VMS = 200

    def __init__(self) -> None:
        self.name = NAME
        self._state = JsonState(NAME, "plans.json")

    @staticmethod
    def _network(cidr: Any) -> Optional[ipaddress.IPv4Network]:
        try:
            return ipaddress.IPv4Network(cidr, strict=True) if isinstance(cidr, str) and "/" in cidr else None
        except ValueError:
            return None

    def validate_config(self, cfg: InfraConfig) -> List[str]:
        if not isinstance(cfg, InfraConfig):
            return ["config must be an InfraConfig"]
        errors = []
        if not is_name(cfg.name, 64):
            errors.append("name: required and must be <=64 chars")
        if cfg.region not in self.SUPPORTED_REGIONS:
            errors.append(f"region: unsupported ({cfg.region})")
        count_ok = isinstance(cfg.vm_count, int) and not isinstance(cfg.vm_count, bool) and \
            self.MIN_VMS <= cfg.vm_count <= self.MAX_VMS
        if not count_ok:
            errors.append(f"vm_count: must be between {self.MIN_VMS} and {self.MAX_VMS}")
        if cfg.vm_type not in self.SUPPORTED_VM_TYPES:
            errors.append(f"vm_type: unsupported ({cfg.vm_type})")
        net = self._network(cfg.network_cidr)
        if net is None:
            errors.append("network_cidr: must be an IPv4 network in CIDR form, e.g. 10.0.0.0/24")
        elif count_ok and net.num_addresses - 2 < cfg.vm_count:
            errors.append(f"network_cidr: {max(0, net.num_addresses - 2)} usable addresses for {cfg.vm_count} VMs")
        if not isinstance(cfg.tags, dict):
            return errors + ["tags: must be an object"]
        for k, v in cfg.tags.items():
            if not isinstance(k, str) or k != k.lower() or " " in k or not k:
                errors.append(f"tags: key '{k}' must be lowercase, no spaces")
            elif not isinstance(v, str):
                errors.append(f"tags: value of '{k}' must be text")
        return errors

    def provision(self, cfg: InfraConfig) -> Dict[str, Any]:
        """Validate and store a plan. Nothing is created: the status is "planned"."""
        errors = self.validate_config(cfg)
        if errors:
            return {"status": "failed", "errors": errors}
        spec = asdict(cfg)
        infra_id = "infra-" + hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:12]
        hosts = self._network(cfg.network_cidr).hosts()
        vms = [{"name": f"{cfg.name}-{i:03d}", "ip": str(next(hosts)), "type": cfg.vm_type}
               for i in range(1, cfg.vm_count + 1)]
        size = VM_SIZES[cfg.vm_type]
        plan = {"infra_id": infra_id, "spec": spec, "vms": vms, "planned_at": time.time(),
                "totals": {"vms": cfg.vm_count, "vcpu": size["vcpu"] * cfg.vm_count, "mem_gb": size["mem_gb"] * cfg.vm_count}}
        self._state.update(lambda d: d.setdefault("plans", {}).setdefault(infra_id, plan))
        return {"status": "planned", "created": False, "infra_id": infra_id, "vms": vms, "totals": plan["totals"],
                "note": "plan stored; no cloud provider is attached, so nothing was created"}

    def get_plan(self, infra_id: str) -> Dict[str, Any]:
        plan = self._state.load().get("plans", {}).get(infra_id) if isinstance(infra_id, str) else None
        return ok(plan=plan) if plan else fail("unknown_infra", "no plan with this id")

    def health_check(self, infra_id: Optional[str] = None, vms: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if infra_id is None and vms is None:
            return {"agent": NAME, "status": "ok", "version": "1.0.0"}
        if not isinstance(vms, list) or not all(
                isinstance(v, dict) and isinstance(v.get("name"), str) and isinstance(v.get("status"), str) for v in vms):
            return invalid("vms must be a list of {'name': ..., 'status': ...}")
        found = self.get_plan(infra_id)
        if found["status"] != "ok":
            return found
        planned = [v["name"] for v in found["plan"]["vms"]]
        reported = {v["name"]: v["status"] for v in vms}
        running = [n for n in planned if reported.get(n) == "running"]
        missing = [n for n in planned if n not in reported]
        unhealthy = [{"name": n, "status": reported[n]} for n in planned if n in reported and reported[n] != "running"]
        health = "healthy" if len(running) == len(planned) else "degraded" if running else "down"
        return ok(infra_id=infra_id, health=health, running=len(running), planned=len(planned), missing=missing,
                  unhealthy=unhealthy, unplanned=sorted(set(reported) - set(planned)))
