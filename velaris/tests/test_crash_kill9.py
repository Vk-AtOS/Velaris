"""KAN-113: a writer killed with SIGKILL mid-write leaves the last good state; schema_version and the migration hook hold."""
import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from velaris.agentkit.recstore import RecordStore
from velaris.agentkit.state import JsonState

ROOT = Path(__file__).resolve().parents[2]
CHILD = textwrap.dedent('''
    import sys
    from velaris.agentkit.recstore import RecordStore
    from velaris.agentkit.state import JsonState
    st = JsonState("CRASH", "s.json", {"n": 0, "pad": ""}, encrypted="test:crash", version=2)
    rs = RecordStore("CRASH", "r", "test:crash")
    n = 0
    while True:
        n += 1
        st.save({"n": n, "pad": "x" * 200000})       # big: the write takes long enough to be interrupted
        rs.put("k", {"n": n, "pad": "y" * 30000})
        print(n, flush=True)
''')


def _kill_after(env, at_least):
    p = subprocess.Popen([sys.executable, "-c", CHILD], cwd=ROOT, env=env, stdout=subprocess.PIPE, text=True)
    last = 0
    for line in p.stdout:
        last = int(line)
        if last >= at_least:
            break
    p.send_signal(signal.SIGKILL)             # kill -9: no cleanup, no atexit, no flush
    p.wait()
    return last


@pytest.mark.parametrize("round_", range(3))
def test_sigkill_mid_write_keeps_the_last_good_state(tmp_path, monkeypatch, round_):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    acked = _kill_after(env, 5 + round_)
    st = JsonState("CRASH", "s.json", {"n": 0, "pad": ""}, encrypted="test:crash", version=2)
    data = st.load()
    assert acked <= data["n"] <= acked + 1                       # the acknowledged save survived; at most the one in flight is also there
    assert len(data["pad"]) == 200000                            # never half a document
    rec = RecordStore("CRASH", "r", "test:crash").get("k")
    assert rec is not None and acked - 1 <= rec["n"] <= acked + 1 and len(rec["pad"]) == 30000
    assert not list(tmp_path.rglob("*.corrupt-*"))               # nothing had to be set aside: the rename is atomic
    st.save({"n": 0, "pad": ""})                                 # and the store is still writable afterwards
    assert st.load()["n"] == 0


def test_schema_version_is_written_and_the_migration_hook_runs_after_a_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    v1 = JsonState("CRASH2", "s.json", {"items": []}, encrypted="test:crash", version=1)
    v1.save({"items": ["a"]})
    assert v1.load() == {"items": ["a"]}
    v2 = JsonState("CRASH2", "s.json", {"items": []}, encrypted="test:crash", version=2,
                   migrations={1: lambda d: {"items": [{"name": i} for i in d["items"]]}})
    assert v2.load() == {"items": [{"name": "a"}]}
    v2.save(v2.load())
    from velaris.agentkit.state import StateVersionError
    with pytest.raises(StateVersionError):
        v1.load()                                                # a newer file is refused, never guessed at
