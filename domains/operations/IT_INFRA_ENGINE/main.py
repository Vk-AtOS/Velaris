# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib
import json

@dataclass
class InfraConfig:
    name: str
    region: str
    vm_count: int
    vm_type: str
    network_cidr: str
    tags: Dict[str, str]

class ITInfraEngine:
    SUPPORTED_REGIONS = {"us-east-1","us-west-2","eu-central-1","ap-south-1"}
    SUPPORTED_VM_TYPES = {"small","medium","large","gpu-1"}
    MIN_VMS = 1
    MAX_VMS = 200

    def _deterministic_int(self, s: str) -> int:
        h = hashlib.sha256(s.encode("utf-8")).hexdigest()
        return int(h[:16], 16)

    def validate_config(self, cfg: InfraConfig) -> List[str]:
        errors = []
        if not cfg.name or len(cfg.name) > 64:
            errors.append("name: required and must be <=64 chars")
        if cfg.region not in self.SUPPORTED_REGIONS:
            errors.append(f"region: unsupported ({cfg.region})")
        if not (self.MIN_VMS <= cfg.vm_count <= self.MAX_VMS):
            errors.append(f"vm_count: must be between {self.MIN_VMS} and {self.MAX_VMS}")
        if cfg.vm_type not in self.SUPPORTED_VM_TYPES:
            errors.append(f"vm_type: unsupported ({cfg.vm_type})")
        if "/" not in cfg.network_cidr or len(cfg.network_cidr.split("/")) != 2:
            errors.append("network_cidr: must be CIDR")
        for k in cfg.tags.keys():
            if k != k.lower() or " " in k:
                errors.append(f"tags: key '{k}' must be lowercase, no spaces")
        return errors

    def provision(self, cfg: InfraConfig) -> Dict[str, Any]:
        errors = self.validate_config(cfg)
        if errors:
            return {"status":"failed","errors":errors}
        base_hash = self._deterministic_int(cfg.name + cfg.region)
        base_id = f"itinfra-{cfg.region}-{base_hash%100000:05d}"
        vms = []
        for i in range(1, cfg.vm_count+1):
            ip_block = (i-1)//254
            ip_host = ((i-1)%254)+1
            vm = {
                "id": f"{base_id}-vm-{i:03d}",
                "type": cfg.vm_type,
                "private_ip": f"10.0.{ip_block}.{ip_host}",
                "status": "provisioned",
                "deterministic_seed": (base_hash + i) % 10**9
            }
            vms.append(vm)
        network = {"id": f"{base_id}-net", "cidr": cfg.network_cidr, "status": "active"}
        return {
            "status": "ok",
            "infrastructure_id": base_id,
            "region": cfg.region,
            "vm_count": cfg.vm_count,
            "vm_template": cfg.vm_type,
            "network": network,
            "vms": vms,
            "tags": cfg.tags
        }

    def health_check(self, infra_id: str, vms: List[Dict[str,Any]]) -> Dict[str, Any]:
        report = {"infrastructure_id": infra_id, "summary": {"total": len(vms),"healthy":0,"degraded":0}, "vms":[]}
        for vm in vms:
            seed = vm.get("deterministic_seed")
            if seed is None:
                seed = self._deterministic_int(vm["id"]) % 1000
            status_flag = (seed % 7 == 0)
            status = "degraded" if status_flag else "healthy"
            report["vms"].append({"id": vm["id"], "status": status})
            if status == "healthy":
                report["summary"]["healthy"] += 1
            else:
                report["summary"]["degraded"] += 1
        return report

# ================================================================================