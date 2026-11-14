"""No bare `except:` and no `except Exception: pass` anywhere in the running code.

A failure that is swallowed without a trace hides data loss (a corrupt session or
identity file quietly replaced by an empty one) and broken delegates reported as "ok".
"""
import ast
import importlib
import logging
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _silent(handler: ast.ExceptHandler) -> bool:
    return all(isinstance(b, (ast.Pass, ast.Continue)) or
               (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant)) for b in handler.body)


def offending_handlers(root: Path = ROOT):
    found = []
    files = [p for d in ("velaris", "departments") for p in (root / d).rglob("*.py")
             if "tests" not in p.parts]
    for path in sorted(files):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as e:
            found.append(f"{path.relative_to(root)}: does not parse ({e.msg})")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            broad = isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException")
            if node.type is None:
                found.append(f"{path.relative_to(root)}:{node.lineno} bare except")
            elif broad and _silent(node):
                found.append(f"{path.relative_to(root)}:{node.lineno} except {node.type.id} swallowed silently")
    return found


def test_no_bare_or_silently_swallowed_exceptions():
    found = offending_handlers()
    assert not found, "\n".join(found)


def test_hfal_corrupt_session_store_is_reported_and_kept(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    from velaris.agents.HFAL.main import HFAL
    first = HFAL()
    token = first.create_session("asha", "4321")
    store = Path(first.SESSION_FILE)
    store.write_text("{ not json")
    with caplog.at_level(logging.WARNING, logger="HFAL"):
        again = HFAL()
    assert any("unreadable" in r.getMessage() for r in caplog.records)     # said so, not silent
    assert again.validate(token, "4321") is False                          # fails closed
    assert Path(str(store) + ".corrupt").read_text() == "{ not json"       # evidence kept, not overwritten


def test_identity_store_corruption_refuses_instead_of_wiping_accounts(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    from velaris.agents.IDENTITY_FRAMEWORK.main import IdentityFramework
    ids = IdentityFramework()
    assert ids.create_identity("asha", "correct horse", {})
    Path(ids.DB_PATH).write_text("{ not json")
    with pytest.raises(RuntimeError, match="corrupt"):
        IdentityFramework()
    assert Path(ids.DB_PATH).read_text() == "{ not json"


def test_memory_fabric_imports_without_a_swallowing_block():
    source = (ROOT / "departments/data_knowledge/MEMORY_FABRIC/main.py").read_text()
    assert "except Exception:\n    pass" not in source
    fabric = importlib.import_module("velaris.agents.MEMORY_FABRIC.main").MemoryFabric()
    fabric.put("ns", "k", 1)
    assert fabric.get("ns", "k") == 1


def test_alias_wrapper_reports_a_failing_delegate_health_check(caplog):
    mod = importlib.import_module("velaris.agents.AEIL.main")

    class Broken:
        @staticmethod
        def health_check():
            raise RuntimeError("delegate down")

    agent = mod.AEILAgent()
    agent._instances = {"BROKEN": Broken}
    with caplog.at_level(logging.WARNING, logger="AEIL"):
        health = agent.health_check()
    assert health["status"] == "degraded" and "delegate down" in health["error"]
    assert any("delegate down" in r.getMessage() for r in caplog.records)


def test_secure_action_token_garbage_is_invalid_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    from velaris.agents.SECURE_ACTION_TOKENS.main import SecureActionTokens
    sat = SecureActionTokens()
    assert sat.validate(sat.generate("pay"), "pay") == {"status": "OK"}
    for bad in ("", "no-dot", "!!!.sig", None, "é.é"):
        assert sat.validate(bad, "pay")["status"] == "INVALID"
