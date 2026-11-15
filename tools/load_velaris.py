#!/usr/bin/env python3.11
"""Load test for the Velaris API (KAN-136): starts it on loopback with throw-away credentials, drives N concurrent signed
users, writes the numbers to tests/load/results/velaris-<UTC>.json and prints them.

  python3.11 tools/load_velaris.py [--users 50] [--seconds 20] [--workers 1] [--out tests/load/results]

What is measured (every request is signed like the gateway signs, so HMAC + Ed25519 + replay cache + trace append are in the path):
  health        GET /health                  unsigned liveness, the floor
  agents        GET /agents                  signed, traced; the first call builds the 346-agent catalogue (reported separately)
  trace_verify  GET /trace/verify            admin only; incremental, checkpointed
  mail_list     GET /mail/mailboxes          signed read of the mail store
Reported per endpoint: requests, errors (non-2xx/refused), throughput, p50/p95/p99 ms. Also: startup seconds, trace entries written
and /trace/verify afterwards (the chain must still be intact after the run). The machine, Python version and CPU count are recorded.
It never contacts anything but 127.0.0.1. It is a design-limit measurement on ONE machine, not a capacity statement for production
(no Redis, no Postgres, no network between gateway and Velaris).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import secrets
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from velaris.api.auth import make_assertion, sign  # noqa: E402

SECRET, ORG = "load-test-secret-" + "x" * 32, "load-org"
VAULT_KEY = "dGVzdC12YXVsdC1rZXktMzItYnl0ZXMtLi4uLi4uLi4="


class Client:
    def __init__(self, base: str, key: Ed25519PrivateKey) -> None:
        self.base, self.key = base, key

    def call(self, method: str, path: str, body: dict | None = None, sub: str = "u1", roles=()) -> int:
        content = json.dumps(body).encode() if body is not None else b""
        nonce = secrets.token_urlsafe(18)
        headers = sign(SECRET.encode(), method, path, content, make_assertion(self.key, sub=sub, org=ORG, roles=roles, nonce=nonce), nonce=nonce)
        req = urllib.request.Request(self.base + path, data=content or None, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                r.read()
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except OSError:
            return 599


def pct(xs: list, p: float) -> float:
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(len(xs) * p))] * 1000, 1) if xs else 0.0


def drive(name: str, fn, users: int, seconds: float) -> dict:
    lat, errs, lock = [], [0], threading.Lock()
    stop = time.monotonic() + seconds

    def worker(i: int) -> None:
        while time.monotonic() < stop:
            t = time.perf_counter()
            code = fn(i)
            dt = time.perf_counter() - t
            with lock:
                lat.append(dt)
                errs[0] += not 200 <= code < 300
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(users)]
    t0 = time.monotonic()
    [t.start() for t in threads]
    [t.join() for t in threads]
    wall = time.monotonic() - t0
    return {"endpoint": name, "users": users, "requests": len(lat), "errors": errs[0], "per_second": round(len(lat) / wall, 1),
            "p50_ms": pct(lat, .5), "p95_ms": pct(lat, .95), "p99_ms": pct(lat, .99), "max_ms": round(max(lat) * 1000, 1) if lat else 0}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--users", type=int, default=50)
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out", type=Path, default=ROOT / "tests" / "load" / "results")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp, socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        key = Ed25519PrivateKey.generate()
        pem = Path(tmp, "identity.pem")
        pem.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        env = {**os.environ, "VELARIS_DATA": str(Path(tmp, "data")), "VELARIS_API_SECRET": SECRET, "VELARIS_ORG": ORG,
               "VELARIS_VAULT_KEY": VAULT_KEY, "VELARIS_IDENTITY_PUBLIC_KEY": str(pem), "VELARIS_API_HOST": "127.0.0.1",
               "VELARIS_API_PORT": str(port), "VELARIS_API_WORKERS": str(a.workers), "PYTHONPATH": str(ROOT)}
        t0 = time.monotonic()
        proc = subprocess.Popen([sys.executable, "-m", "velaris.api"], env=env, cwd=tmp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base, cl = f"http://127.0.0.1:{port}", Client(f"http://127.0.0.1:{port}", key)
        try:
            for _ in range(240):
                try:
                    urllib.request.urlopen(base + "/health", timeout=2).read()
                    break
                except OSError:
                    time.sleep(0.5)
            else:
                print("the API did not start", file=sys.stderr)
                return 1
            startup = round(time.monotonic() - t0, 1)
            t = time.perf_counter()
            first = cl.call("GET", "/agents")
            first_agents_s = round(time.perf_counter() - t, 2)
            results = [drive("health", lambda i: urllib.request.urlopen(base + "/health", timeout=30).status, a.users, a.seconds),
                       drive("agents", lambda i: cl.call("GET", "/agents", sub=f"u{i}"), a.users, a.seconds),
                       drive("trace_verify", lambda i: cl.call("GET", "/trace/verify", sub=f"u{i}", roles=["governance_admin"]), a.users, a.seconds),
                       drive("mail_list", lambda i: cl.call("GET", "/mail/mailboxes", sub=f"u{i}"), a.users, a.seconds)]
            verify_code = cl.call("GET", "/trace/verify", roles=["governance_admin"])
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
        trace_file = Path(tmp, "data", "trace.jsonl")
        report = {"when_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tool": "tools/load_velaris.py", "users": a.users,
                  "seconds_per_endpoint": a.seconds, "workers": a.workers, "startup_s": startup, "first_agents_call_s": first_agents_s,
                  "first_agents_status": first, "trace_entries_after": sum(1 for _ in trace_file.open()) if trace_file.exists() else 0,
                  "trace_verify_after_status": verify_code, "results": results,
                  "machine": {"platform": platform.platform(), "python": platform.python_version(), "cpus": os.cpu_count()},
                  "caveat": "one machine, loopback, no Redis/Postgres, other processes may share the CPU: a design measurement, not a production capacity figure"}
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / f"velaris-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"\nwritten: {path}")
    return 0 if all(r["errors"] == 0 for r in results) else 2


if __name__ == "__main__":
    sys.exit(main())
