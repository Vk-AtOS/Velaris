"""KAN-112: the packaging files agree with each other and cannot quietly ship a secret or publish the internal API."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"


def test_constraints_pin_every_runtime_requirement():
    pinned = {ln.split("==")[0].lower() for ln in (DEPLOY / "constraints.txt").read_text().splitlines() if "==" in ln}
    wanted = {re.split(r"[<>=\s]", ln)[0].lower() for ln in (ROOT / "requirements.txt").read_text().splitlines()
              if ln and not ln.startswith(("#", "pytest"))}
    assert wanted <= pinned, wanted - pinned
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[0-9][A-Za-z0-9.]*", ln) for ln in (DEPLOY / "constraints.txt").read_text().splitlines()
               if ln and not ln.startswith("#"))


def test_dockerfile_runs_non_root_with_healthcheck():
    d = (DEPLOY / "Dockerfile").read_text()
    assert re.search(r"^USER velaris", d, re.M) and "HEALTHCHECK" in d and "python:3.11-slim" in d and "VELARIS_DATA=/data" in d
    assert "workers" not in d.split("CMD")[-1] and "COPY . " not in d


def test_compose_never_publishes_the_api():
    yaml = pytest.importorskip("yaml")
    c = yaml.safe_load((DEPLOY / "docker-compose.example.yml").read_text())
    assert "ports" not in c["services"]["api"] and c["networks"]["internal"]["internal"] is True
    assert c["services"]["public"]["ports"] == ["127.0.0.1:8731:8731"]
    assert c["x-velaris"]["read_only"] is True


def test_k8s_has_no_secret_values_and_a_gateway_only_policy():
    yaml = pytest.importorskip("yaml")
    docs = [d for d in yaml.safe_load_all((DEPLOY / "k8s" / "velaris.yaml").read_text()) if d]
    kinds = [d["kind"] for d in docs]
    assert "Secret" not in kinds and {"PersistentVolumeClaim", "Deployment", "Service", "NetworkPolicy"} <= set(kinds)
    assert all(d["spec"]["type"] == "ClusterIP" for d in docs if d["kind"] == "Service")
    api_policy = next(d for d in docs if d["kind"] == "NetworkPolicy" and "api" in d["metadata"]["name"])
    assert api_policy["spec"]["policyTypes"] == ["Ingress"]
    gateway = api_policy["spec"]["ingress"][0]["from"][0]
    assert "namespaceSelector" in gateway and "podSelector" in gateway
    for d in docs:
        if d["kind"] == "Deployment":
            c = d["spec"]["template"]["spec"]["containers"][0]
            assert c["securityContext"]["readOnlyRootFilesystem"] is True
            assert all("value" not in e or e["name"] not in ("VELARIS_API_SECRET", "VELARIS_ORG") for e in c["env"])


def test_templates_hold_placeholders_only():
    for p in [*DEPLOY.rglob("*.example*"), *DEPLOY.rglob("*.service")]:
        text = p.read_text()
        assert not re.search(r"-----BEGIN [A-Z ]*KEY-----\s*\S{20,}", text), p
        for m in re.finditer(r"(?:SECRET|PASSWORD|TOKEN)=(\S+)", text):
            assert m.group(1).startswith(("CHANGE_ME", "$", "${")) or m.group(1) == "", (p, m.group(1))
