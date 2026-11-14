#!/usr/bin/env python3.11
"""Smoke test: start the API locally with dummy credentials and check the two things that must always hold.

  1. GET /health answers 200.
  2. An unsigned request, and one signed with the wrong secret, are refused (401). A correctly signed request is accepted.

Usage (repository root):  python3.11 deploy/smoke.py       Exit 0 = pass. Uses a temp VELARIS_DATA; touches nothing else.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from velaris.api.auth import make_assertion, sign  # noqa: E402

SECRET = "smoke-test-secret-" + "x" * 32
ORG = "smoke-org"


def call(url, headers=None, method="GET"):
    req = urllib.request.Request(url, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def main():
    with tempfile.TemporaryDirectory() as tmp, socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        key = Ed25519PrivateKey.generate()
        pem = Path(tmp, "identity.pem")
        pem.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        env = {**os.environ, "VELARIS_DATA": str(Path(tmp, "data")), "VELARIS_API_SECRET": SECRET, "VELARIS_ORG": ORG,
               "VELARIS_IDENTITY_PUBLIC_KEY": str(pem), "VELARIS_API_HOST": "127.0.0.1", "VELARIS_API_PORT": str(port),
               "PYTHONPATH": str(ROOT)}
        proc = subprocess.Popen([sys.executable, "-m", "velaris.api"], env=env, cwd=tmp, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(60):
                if proc.poll() is not None:
                    raise SystemExit("FAIL: the API exited: " + proc.stderr.read().decode()[-500:])
                try:
                    if call(base + "/health") == 200:
                        break
                except OSError:
                    time.sleep(0.5)
            else:
                raise SystemExit("FAIL: /health did not answer in 30 s")
            assert call(base + "/agents") == 401, "unsigned request was not refused"
            assert call(base + "/trace/verify") == 401, "unsigned request was not refused"
            nonce = "smoke-nonce-wrong-secret-1"
            bad = sign(b"w" * 40, "GET", "/trace/verify", b"", make_assertion(key, sub="u", org=ORG, nonce=nonce), nonce=nonce)
            assert call(base + "/trace/verify", bad) == 401, "wrong-secret request was not refused"
            nonce = "smoke-nonce-good-request-1"
            good = sign(SECRET.encode(), "GET", "/trace/verify", b"", make_assertion(key, sub="u", org=ORG, nonce=nonce), nonce=nonce)
            assert call(base + "/trace/verify", good) == 200, "a correctly signed request was refused"
        finally:
            proc.terminate()
            proc.wait(timeout=10)
    print(json.dumps({"smoke": "ok"}))


if __name__ == "__main__":
    main()
