"""VIGILIS: signatures, a deny-by-default policy check, and a file-integrity watch.

Signing      generate_test_keypair() makes an in-memory RSA-2048 key; sign_message()
             and verify_signature() use RSA-PSS with SHA-256. Verification fails
             closed: any error, a missing key or a non-bytes argument is "not valid".
             The key lives only in this object - it is for signing within one
             process (and tests), not a key-management service.

Policy       evaluate_policy(context) applies config["policies"], a list of
             {"id": ..., "effect": "allow"|"deny", "when": {conditions}}
             (conditions as in velaris.agentkit.infra_policy). A matching deny
             wins; otherwise a matching allow is needed. No policies, a malformed
             policy list, or context["untrusted_source"] being set: denied.
             (POLICY_CONTROLLER is the stored, versioned policy set; this is a
             check against the configuration this agent was started with.)

Integrity    baseline(paths) records the SHA-256 of files (by default every
             agent's main.py); check() reports each file that has since changed
             or disappeared. The baseline is an owner-only file, not a signed
             one: it detects accidental or unprivileged change, not an attacker
             who can also rewrite the baseline.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from velaris import agents
from velaris.agentkit import infra_policy
from velaris.agentkit.infra_store import State, fail, invalid
from velaris.core.utils import sha256_of_file

logger = logging.getLogger("VIGILIS")
NAME = "VIGILIS"
MAX_WATCHED = 5000


def _pss() -> padding.PSS:
    return padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)


class VigilisAgent:
    def __init__(self, config: Optional[dict] = None) -> None:
        self.config = config if isinstance(config, dict) else {}
        self.name = NAME
        self.version = self.config.get("version", "1.0.0")
        self._private_key_pem: Optional[bytes] = None
        self._public_key_pem: Optional[bytes] = None
        self._state = State(NAME, "baseline.json")

    def health_check(self) -> dict:
        return {"agent": self.name, "version": self.version, "status": "ok"}

    # ── signing ──────────────────────────────────────────────────────────────
    def generate_test_keypair(self) -> Tuple[bytes, bytes]:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._private_key_pem = key.private_bytes(encoding=serialization.Encoding.PEM,
                                                  format=serialization.PrivateFormat.PKCS8,
                                                  encryption_algorithm=serialization.NoEncryption())
        self._public_key_pem = key.public_key().public_bytes(encoding=serialization.Encoding.PEM,
                                                             format=serialization.PublicFormat.SubjectPublicKeyInfo)
        return self._private_key_pem, self._public_key_pem

    def sign_message(self, message: bytes) -> bytes:
        """RSA-PSS signature of `message`, or b"" (which never verifies) if there is no key or message is not bytes."""
        if self._private_key_pem is None or not isinstance(message, (bytes, bytearray)):
            logger.warning("sign_message refused: no key generated or message is not bytes")
            return b""
        key = serialization.load_pem_private_key(self._private_key_pem, password=None)
        return key.sign(bytes(message), _pss(), hashes.SHA256())

    def verify_signature(self, message: bytes, signature: bytes) -> bool:
        if self._public_key_pem is None or not all(isinstance(v, (bytes, bytearray)) for v in (message, signature)):
            return False
        try:
            serialization.load_pem_public_key(self._public_key_pem).verify(
                bytes(signature), bytes(message), _pss(), hashes.SHA256())
            return True
        except (InvalidSignature, ValueError, TypeError) as e:
            logger.warning("Signature verification failed: %s", type(e).__name__)
            return False

    # ── policy ───────────────────────────────────────────────────────────────
    def evaluate_policy(self, context: dict) -> dict:
        def denied(status: str, reason: str, rule: Optional[str] = None) -> dict:
            return {"allowed": False, "status": status, "reasons": [reason], "rule": rule}
        if not isinstance(context, dict):
            return denied("invalid_input", "context must be an object")
        if context.get("untrusted_source"):
            return denied("ok", "untrusted_source flag present")
        policies = self.config.get("policies")
        if not policies:
            return denied("no_policy", "no policies configured: denied by default")
        well_formed = isinstance(policies, list) and all(
            isinstance(p, dict) and isinstance(p.get("id"), str) and p.get("effect") in ("allow", "deny")
            and not infra_policy.problems(p.get("when")) for p in policies)
        if not well_formed:
            return denied("invalid_policy", "configured policies are malformed: denied")
        matching = [p for p in policies if infra_policy.evaluate(p["when"], context, p["effect"])[0]]
        for effect in ("deny", "allow"):
            hit = next((p for p in matching if p["effect"] == effect), None)
            if hit:
                return {"allowed": effect == "allow", "status": "ok", "rule": hit["id"],
                        "reasons": [f"{'allowed' if effect == 'allow' else 'denied'} by policy {hit['id']}"]}
        return denied("ok", "no policy allows this context")

    # ── integrity ────────────────────────────────────────────────────────────
    @staticmethod
    def _agent_sources() -> List[str]:
        return [str(f / "main.py") for d in agents.department_dirs() for f in sorted(d.iterdir())
                if (f / "main.py").is_file()]

    def baseline(self, paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Record the current SHA-256 of each file (default: every agent's main.py)."""
        targets = self._agent_sources() if paths is None else paths
        if not isinstance(targets, list) or not targets or len(targets) > MAX_WATCHED or not all(
                isinstance(p, str) and os.path.isabs(p) for p in targets):
            return invalid(f"paths must be a list of 1 to {MAX_WATCHED} absolute file paths")
        hashes_by_path = {p: sha256_of_file(p) if os.path.isfile(p) else None for p in targets}
        missing = sorted(p for p, h in hashes_by_path.items() if h is None)
        if missing:
            return fail("rejected", "these are not readable files: " + ", ".join(missing[:5]))
        self._state.save({"files": hashes_by_path})
        return {"status": "ok", "files": len(hashes_by_path)}

    def check(self) -> Dict[str, Any]:
        """Compare the watched files with the baseline. Each difference is a "high" finding."""
        files = self._state.load().get("files")
        if not files:
            return {"status": "no_baseline", "intact": False, "findings": [],
                    "reason": "baseline() has not been run; integrity is unknown"}
        findings = []
        for path, expected in sorted(files.items()):
            actual = sha256_of_file(path) if os.path.isfile(path) else None
            if actual != expected:
                findings.append({"severity": "high", "check": "integrity", "path": path,
                                 "detail": "file is missing" if actual is None else "content changed since baseline"})
        return {"status": "ok", "intact": not findings, "checked": len(files), "findings": findings}


if __name__ == "__main__":
    print(json.dumps(VigilisAgent().health_check()))
