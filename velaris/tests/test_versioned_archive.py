"""KAN-167: a VersionedDoc past 1,000 versions archives the oldest instead of refusing writes."""
from velaris.agentkit import aicore_b_versioned as av
from velaris.agentkit.aicore_b_versioned import VersionedDoc


def test_history_past_the_cap_is_archived_not_refused(monkeypatch):
    monkeypatch.setattr(av, "MAX_VERSIONS", 10)
    d = VersionedDoc("VD_TEST", "doc.json", {"n": 0})
    for i in range(1, 26):
        assert d.update({"n": i}, "tester")["status"] == "ok"
    assert d.version() == 25 and d.current() == {"n": 25}
    assert [h["version"] for h in d.history()] == list(range(1, 26))      # nothing lost
    assert d.rollback(2, "tester")["status"] == "ok" and d.current() == {"n": 2}   # an archived version is still reachable
