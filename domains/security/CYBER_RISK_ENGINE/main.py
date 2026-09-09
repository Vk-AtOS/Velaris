# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib
import json

@dataclass
class AssetProfile:
    asset_id: str
    asset_type: str
    criticality: str
    exposure_points: int
    controls: Dict[str, bool]

class CyberRiskEngine:
    SUPPORTED_ASSET_TYPES = {"server","database","endpoint","network-device"}
    SUPPORTED_CRITICALITY = {"low","medium","high","critical"}
    MAX_EXPOSURE = 500
    CONTROL_WEIGHTS = {
        "firewall": 25,
        "ids": 20,
        "patching": 30,
        "encryption": 15,
        "network_seg": 10
    }

    def _hash(self, s: str) -> int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12], 16)

    def validate(self, p: AssetProfile) -> List[str]:
        errors = []
        if not p.asset_id or len(p.asset_id) > 64:
            errors.append("asset_id invalid")
        if p.asset_type not in self.SUPPORTED_ASSET_TYPES:
            errors.append(f"unsupported asset_type ({p.asset_type})")
        if p.criticality not in self.SUPPORTED_CRITICALITY:
            errors.append(f"unsupported criticality ({p.criticality})")
        if p.exposure_points < 0 or p.exposure_points > self.MAX_EXPOSURE:
            errors.append("exposure_points out of range")
        for c in p.controls.keys():
            if c not in self.CONTROL_WEIGHTS:
                errors.append(f"unsupported control ({c})")
        return errors

    def compute_risk(self, p: AssetProfile) -> Dict[str, Any]:
        errors = self.validate(p)
        if errors:
            return {"status": "failed", "errors": errors}

        base = self._hash(p.asset_id + p.asset_type)
        crit_factor = {"low":1,"medium":2,"high":3,"critical":4}[p.criticality]
        exposure_score = p.exposure_points * crit_factor

        control_score = 0
        for k,v in p.controls.items():
            if v:
                control_score += self.CONTROL_WEIGHTS[k]

        raw_risk = (exposure_score + base % 500) - control_score
        normalized = max(0, min(1000, raw_risk))

        if normalized < 250:
            tier = "low"
        elif normalized < 500:
            tier = "moderate"
        elif normalized < 750:
            tier = "high"
        else:
            tier = "critical"

        return {
            "status":"ok",
            "asset_id":p.asset_id,
            "risk_score":normalized,
            "risk_tier":tier,
            "details":{
                "exposure_score":exposure_score,
                "control_score":control_score,
                "base_entropy":base % 500
            }
        }

if __name__ == "__main__":
    sample = AssetProfile(
        asset_id="srv-001",
        asset_type="server",
        criticality="high",
        exposure_points=120,
        controls={"firewall":True,"ids":True,"patching":False}
    )
    eng = CyberRiskEngine()
    print(json.dumps(eng.compute_risk(sample), indent=2))

# ================================================================================