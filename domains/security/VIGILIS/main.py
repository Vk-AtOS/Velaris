"""
VIGILIS - Security & Trust Agent (minimal implementation)

Placeholders:
 - health_check(): returns agent status
 - sign_message()/verify_signature(): simple RSA signing/verification helper stubs
 - evaluate_policy(): simple policy check placeholder

This file is intentionally self-contained and lightweight for initial tests.
"""

import os
import json
import logging
from typing import Tuple

logger = logging.getLogger("VIGILIS")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - VIGILIS - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class VigilisAgent:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.name = "VIGILIS"
        self.version = self.config.get("version", "0.1.0")
        # Simple in-memory keypair for test purposes (not secure); used only for tests.
        self._private_key_pem = None
        self._public_key_pem = None

    def health_check(self) -> dict:
        """Return basic health/status information."""
        status = {
            "agent": self.name,
            "version": self.version,
            "status": "ok",
        }
        logger.debug("Health check: %s", status)
        return status

    def generate_test_keypair(self) -> Tuple[bytes, bytes]:
        """Generate a simple RSA keypair for testing (uses cryptography if available)."""
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa, padding
            from cryptography.hazmat.primitives import serialization, hashes
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            priv_pem = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
            pub_pem = key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            self._private_key_pem = priv_pem
            self._public_key_pem = pub_pem
            logger.debug("Generated test RSA keypair.")
            return priv_pem, pub_pem
        except Exception as e:
            logger.warning("cryptography not available - returning dummy keys. (%s)", e)
            priv = b"TEST_PRIVATE_KEY"
            pub = b"TEST_PUBLIC_KEY"
            self._private_key_pem = priv
            self._public_key_pem = pub
            return priv, pub

    def sign_message(self, message: bytes) -> bytes:
        """Sign message using generated private key (best-effort)."""
        if self._private_key_pem is None:
            raise RuntimeError("No private key - call generate_test_keypair() first.")
        try:
            from cryptography.hazmat.primitives import serialization, hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            priv = serialization.load_pem_private_key(self._private_key_pem, password=None)
            signature = priv.sign(
                message,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
            logger.debug("Message signed.")
            return signature
        except Exception:
            # Fallback deterministic 'signature' for environments without cryptography
            sig = b"SIG:" + message[::-1][:32]
            logger.debug("Fallback signing used.")
            return sig

    def verify_signature(self, message: bytes, signature: bytes) -> bool:
        """Verify signature for message (best-effort)."""
        if self._public_key_pem is None:
            raise RuntimeError("No public key - call generate_test_keypair() first.")
        try:
            from cryptography.hazmat.primitives import serialization, hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            pub = serialization.load_pem_public_key(self._public_key_pem)
            pub.verify(
                signature,
                message,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
            logger.debug("Signature verified (cryptography).")
            return True
        except Exception:
            # Fallback deterministic check for fallback signature
            expected = b"SIG:" + message[::-1][:32]
            ok = signature == expected
            logger.debug("Fallback signature verification: %s", ok)
            return ok

    def evaluate_policy(self, context: dict) -> dict:
        """
        Evaluate a simple security/trust policy.
        This placeholder returns a pass/fail for provided context keys.
        """
        policies = self.config.get("policies", {})
        result = {"allowed": True, "reasons": []}
        # Example simple check: reject if 'untrusted_source' in context
        if context.get("untrusted_source"):
            result["allowed"] = False
            result["reasons"].append("untrusted_source flag present")
        logger.debug("Policy evaluation result: %s", result)
        return result

if __name__ == "__main__":
    # Basic smoke-run when executed directly
    agent = VigilisAgent()
    print(json.dumps(agent.health_check()))
