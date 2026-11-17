"""Every agent folder has a manifest, the registry sees it, and health never invents an ok (KAN-95)."""
import json

from velaris.agents import department_dirs
from velaris.agents.health import default_health
from velaris.agents.REGISTRY.main import AgentRegistry


def test_every_agent_folder_has_a_valid_manifest():
    missing, bad = [], []
    for d in department_dirs():
        for a in sorted(d.iterdir()):
            if not (a / "main.py").exists():
                continue
            if not (a / "manifest.json").exists():
                missing.append(a.name)
                continue
            m = json.loads((a / "manifest.json").read_text())
            if m.get("name") != a.name or ":" not in str(m.get("entrypoint")) or not m.get("description"):
                bad.append(a.name)
    assert not missing and not bad, (missing, bad)


def test_registry_builds_class_of_every_manifest():
    r = AgentRegistry()
    assert len(r.list_agents()) >= 346
    for name in r.list_agents():
        assert isinstance(r.get_agent_class(name), type), name


def test_default_health_is_honest():
    class A:
        pass

    class B:
        def health(self):
            return {"status": "ok"}

    class M:
        @staticmethod
        def health_check():
            return {"status": "degraded"}

    assert default_health("A", A(), object())["status"] == "probed"
    assert default_health("B", B(), object())["status"] == "ok"
    assert default_health("A", A(), M)["status"] == "degraded"


def test_health_all_never_reports_ok_for_agent_without_method():
    h = AgentRegistry().health_all()
    assert h["LYRA"]["status"] == "probed" and h["LYRA"]["public_methods"] > 0
    assert not any(v.get("status") == "no_health_check" for v in h.values())


def test_the_health_contract_names_needs_key_and_probed_apart_from_error(monkeypatch):
    from velaris.agents.health import STATUSES, HealthCheck, build_failure
    from velaris.core.vault import VaultKeyError
    monkeypatch.delenv("VELARIS_VAULT_KEY", raising=False)
    monkeypatch.delenv("VELARIS_VAULT_KEY_FILE", raising=False)
    h = AgentRegistry().health_all()
    assert {n for n, v in h.items() if v["status"] == "needs_key"} >= {"EMPLOYEE_RECORDS", "LEAVE_MANAGEMENT", "RECRUITMENT_ATS"}
    assert h["LEAVE_MANAGEMENT"]["needs"] == ["VELARIS_VAULT_KEY or VELARIS_VAULT_KEY_FILE"]      # names, never a value
    assert not any(v["status"] in ("error", "no_health_method") for v in h.values())
    assert all(v["status"] in STATUSES or v["status"] == "unknown" for v in h.values())
    assert build_failure("X", ValueError("boom"))["status"] == "error" and build_failure("X", VaultKeyError("k"))["status"] == "needs_key"

    class Mine:
        def health_check(self):
            return {"status": "ok"}
    assert isinstance(Mine(), HealthCheck) and not isinstance(object(), HealthCheck)
