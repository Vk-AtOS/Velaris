import importlib

import pytest


@pytest.fixture
def chain(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    mod = importlib.import_module("departments.security.SIGNED_AUDIT_CHAIN.main")
    return mod.SignedAuditChain()


def _lines(chain):
    return open(chain.CHAIN_PATH).read().splitlines()


def test_several_events_verify(chain):
    for i in range(3):
        chain.append_event("a", "act", {"i": i})
    assert len(_lines(chain)) == 3          # one line per event (the terminator used to be "/n")
    assert chain.verify_chain()


def test_removed_or_reordered_entry_is_detected(chain):
    for i in range(3):
        chain.append_event("a", "act", {"i": i})
    lines = _lines(chain)
    for tampered in ([lines[0], lines[2]], [lines[1], lines[0], lines[2]]):
        open(chain.CHAIN_PATH, "w").write("\n".join(tampered) + "\n")
        assert not chain.verify_chain()
