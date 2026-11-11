# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import json
from velaris.core.utils import not_implemented

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
        return not_implemented("IT_INFRA_ENGINE.provision", "previous version mixed sha256(id) noise into the result; no real model exists yet")

    def health_check(self, infra_id: str, vms: List[Dict[str,Any]]) -> Dict[str, Any]:
        return not_implemented("IT_INFRA_ENGINE.health_check", "previous version mixed sha256(id) noise into the result; no real model exists yet")

# ================================================================================