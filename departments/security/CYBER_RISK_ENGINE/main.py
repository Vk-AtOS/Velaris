"""CYBER_RISK_ENGINE: a residual-risk score for a declared asset, by a stated formula.

Inputs are what the caller declares: the asset's criticality, its exposure
points (open ports, public endpoints, external integrations, ...), which
controls are in place, and optionally the threats in play with a likelihood each.

    exposure      = exposure_points / MAX_EXPOSURE                         (0..1)
    threat        = 1 - product(1 - likelihood_i)                          (0 when none declared)
    likelihood    = 1 - (1 - exposure) * (1 - threat)
    impact        = CRITICALITY_IMPACT[criticality]                        (0.25 .. 1.0)
    inherent      = 100 * likelihood * impact
    effectiveness = sum(CONTROL_WEIGHTS of controls in place) / 100        (0..1)
    residual      = inherent * (1 - MAX_CONTROL_REDUCTION * effectiveness)

Controls never remove more than MAX_CONTROL_REDUCTION of the risk. Bands: residual
>= 70 critical, >= 40 high, >= 15 medium, else low. The same inputs always give
the same score; the asset id plays no part in it. The weights are this engine's
declared model, not a measurement of any real network.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from velaris.agentkit.checks import is_name, is_number
from velaris.agentkit.results import ok
from velaris.agentkit.state import JsonState
from velaris.core.access import SECURITY_ADMINS, check_caller

NAME = "CYBER_RISK_ENGINE"
CRITICALITY_IMPACT = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}
MAX_CONTROL_REDUCTION = 0.8
BANDS = ((70, "critical"), (40, "high"), (15, "medium"), (0, "low"))


@dataclass
class AssetProfile:
    asset_id: str
    asset_type: str
    criticality: str
    exposure_points: int
    controls: Dict[str, bool]


class CyberRiskEngine:
    SUPPORTED_ASSET_TYPES = {"server", "database", "endpoint", "network-device"}
    SUPPORTED_CRITICALITY = set(CRITICALITY_IMPACT)
    MAX_EXPOSURE = 500
    CONTROL_WEIGHTS = {"firewall": 25, "ids": 20, "patching": 30, "encryption": 15, "network_seg": 10}

    def __init__(self) -> None:
        self.name = NAME
        self._state = JsonState(NAME, "register.json")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": NAME, "status": "ok", "version": "1.0.0"}

    def validate(self, p: AssetProfile) -> List[str]:
        if not isinstance(p, AssetProfile):
            return ["profile must be an AssetProfile"]
        errors = []
        if not is_name(p.asset_id, 64):
            errors.append("asset_id invalid")
        if p.asset_type not in self.SUPPORTED_ASSET_TYPES:
            errors.append(f"unsupported asset_type ({p.asset_type})")
        if p.criticality not in self.SUPPORTED_CRITICALITY:
            errors.append(f"unsupported criticality ({p.criticality})")
        if not is_number(p.exposure_points, 0, self.MAX_EXPOSURE):
            errors.append("exposure_points out of range")
        if not isinstance(p.controls, dict):
            return errors + ["controls must be an object"]
        for c, in_place in p.controls.items():
            if c not in self.CONTROL_WEIGHTS:
                errors.append(f"unsupported control ({c})")
            elif not isinstance(in_place, bool):
                errors.append(f"control {c} must be true or false")
        return errors

    @staticmethod
    def _threat_errors(threats: Any) -> List[str]:
        if threats is None:
            return []
        if not isinstance(threats, list) or not all(
                isinstance(t, dict) and is_name(t.get("name")) and is_number(t.get("likelihood"), 0, 1) for t in threats):
            return ["threats must be a list of {'name': ..., 'likelihood': 0..1}"]
        return []

    def compute_risk(self, p: AssetProfile, threats: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        errors = self.validate(p) + self._threat_errors(threats)
        if errors:
            return {"status": "failed", "errors": errors}
        exposure = p.exposure_points / self.MAX_EXPOSURE
        no_threat = 1.0
        for t in threats or []:
            no_threat *= 1 - t["likelihood"]
        likelihood = 1 - (1 - exposure) * no_threat
        inherent = 100 * likelihood * CRITICALITY_IMPACT[p.criticality]
        in_place = sum(w for c, w in self.CONTROL_WEIGHTS.items() if p.controls.get(c) is True)
        residual = inherent * (1 - MAX_CONTROL_REDUCTION * in_place / 100)
        missing = [{"control": c, "weight": w,
                    "residual_if_added": round(inherent * (1 - MAX_CONTROL_REDUCTION * (in_place + w) / 100), 2)}
                   for c, w in sorted(self.CONTROL_WEIGHTS.items(), key=lambda cw: (-cw[1], cw[0]))
                   if p.controls.get(c) is not True]
        return ok(asset_id=p.asset_id, score=round(residual, 2), inherent=round(inherent, 2),
                  likelihood=round(likelihood, 4), impact=CRITICALITY_IMPACT[p.criticality],
                  control_effectiveness=in_place / 100, band=next(b for floor, b in BANDS if residual >= floor),
                  missing_controls=missing)

    def register(self, p: AssetProfile, threats: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Score an asset and keep the result in the risk register (latest assessment per asset)."""
        result = self.compute_risk(p, threats)
        if result["status"] == "ok":
            _, refused = check_caller(NAME, "register", {"asset": p.asset_id, "score": result["score"]},
                                      roles=SECURITY_ADMINS)
            if refused:
                return refused
            entry = {"profile": asdict(p), "threats": threats or [], "score": result["score"], "band": result["band"]}
            self._state.update(lambda d: d.setdefault("assets", {}).__setitem__(p.asset_id, entry))
        return result

    def top_risks(self, n: int = 10) -> List[Dict[str, Any]]:
        """The n highest-scoring registered assets, worst first."""
        if not is_number(n, 1) or isinstance(n, float):
            return []
        assets = self._state.load().get("assets", {})
        ranked = sorted(assets.items(), key=lambda kv: (-kv[1]["score"], kv[0]))
        return [{"asset_id": a, "score": e["score"], "band": e["band"]} for a, e in ranked[:n]]
