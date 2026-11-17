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

    assert default_health("A", A(), object())["status"] == "no_health_method"
    assert default_health("B", B(), object())["status"] == "ok"
    assert default_health("A", A(), M)["status"] == "degraded"


def test_health_all_never_reports_ok_for_agent_without_method():
    h = AgentRegistry().health_all()
    assert h["LYRA"]["status"] == "no_health_method"
    assert not any(v.get("status") == "no_health_check" for v in h.values())
