"""Surfaces: stale snapshots, jail, checkpoint + undo, terminal allow-list, browser gate, desktop stub."""
import os

import pytest

from velaris.control.browser import BrowserSurface, host_allowed
from velaris.control.checkpoint import CheckpointStore, Journal, compensators
from velaris.control.core import Action, Refused, StaleSnapshot
from velaris.control.desktop import DesktopSurface
from velaris.control.fake import FakeDriver
from velaris.control.files import FilesSurface, resolve_in
from velaris.control.terminal import DEFAULT_ALLOW, CommandSpec, RunResult, TerminalSurface, argv_for


@pytest.fixture
def jail(tmp_path):
    d = tmp_path / "jail"
    d.mkdir()
    (d / "a.txt").write_bytes(b"alpha\n")
    (d / "b.pdf").write_bytes(b"%PDF-1")
    return d


@pytest.fixture
def store(tmp_path):
    return CheckpointStore(tmp_path / "cp")


def files(jail, store, task="t1", **kw):
    return FilesSurface(jail, journal=Journal(store, task, "acme"), **kw)


def ref(obs, name):
    return next(e.ref for e in obs.elements if e.name == name)


def test_stale_or_missing_snapshot_is_rejected(jail, store):
    s = files(jail, store)
    obs = s.observe()
    with pytest.raises(StaleSnapshot):
        s.act(Action("read", ref(obs, "a.txt")), None)
    with pytest.raises(StaleSnapshot):
        s.act(Action("read", ref(obs, "a.txt")), "deadbeef")
    assert s.act(Action("read", ref(obs, "a.txt")), obs.snapshot_id).output == "alpha\n"
    (jail / "new.txt").write_text("x")                      # the world changes behind the observation
    with pytest.raises(StaleSnapshot):
        s.act(Action("read", ref(obs, "a.txt")), obs.snapshot_id)
    with pytest.raises(Refused):                             # a ref that is not in that snapshot
        s.act(Action("read", "e99"), s.observe().snapshot_id)


@pytest.mark.parametrize("bad", ["../x", "/etc/passwd", "a/../../x", "~/x", "a\x00b", "", "a\\b", "..", "x/.."])
def test_jail_refuses_escapes(jail, bad):
    with pytest.raises(Refused):
        resolve_in(jail.resolve(), bad)


def test_jail_refuses_symlinks_and_hardlinks(jail, store, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("top secret")
    os.symlink(outside, jail / "link.txt")
    os.symlink(tmp_path, jail / "dirlink")
    os.link(outside, jail / "hard.txt")
    s = files(jail, store)
    obs = s.observe()
    roles = {e.name: e.role for e in obs.elements}
    assert roles["link.txt"] == "symlink" and roles["dirlink"] == "symlink"
    with pytest.raises(Refused):
        s.classify(Action("read", "e1"), next(e for e in obs.elements if e.name == "link.txt"))
    with pytest.raises(Refused):
        resolve_in(jail.resolve(), "dirlink/secret.txt")
    with pytest.raises(Refused):
        s.read_bytes("link.txt")
    with pytest.raises(Refused):
        s.read_bytes("hard.txt")                              # two links: could be a door out of the jail
    assert (outside.read_text()) == "top secret"


def test_checkpoint_and_undo_restore_byte_for_byte(jail, store):
    s = files(jail, store)
    original = {p.name: p.read_bytes() for p in jail.iterdir()}
    for kind, name, kw in [("write", "a.txt", {"value": "changed"}), ("move", "b.pdf", {"to": "moved.pdf"})]:
        obs = s.observe()
        s.act(Action(kind, ref(obs, name), **kw), obs.snapshot_id)
    obs = s.observe()
    s.act(Action("mkdir", ref(obs, "."), to="sub"), obs.snapshot_id)
    obs = s.observe()
    s.act(Action("create", ref(obs, "."), "hello", "sub/new.txt"), obs.snapshot_id)
    obs = s.observe()
    s.act(Action("delete", ref(obs, "moved.pdf")), obs.snapshot_id)
    assert not (jail / "moved.pdf").exists() and (jail / "a.txt").read_text() == "changed"
    out = store.undo("t1", "acme", s.undo_handlers())
    assert out["conflicts"] == [] and len(out["undone"]) == 5
    assert {p.name: p.read_bytes() for p in jail.iterdir()} == original       # byte for byte, and nothing else left
    assert store.undo("t1", "acme", s.undo_handlers())["undone"] == []        # idempotent


def test_undo_does_not_clobber_later_changes_and_never_crosses_orgs(jail, store):
    s = files(jail, store)
    obs = s.observe()
    s.act(Action("write", ref(obs, "a.txt"), "task version"), obs.snapshot_id)
    (jail / "a.txt").write_text("someone else edited this afterwards")
    out = store.undo("t1", "acme", s.undo_handlers())
    assert out["undone"] == [] and "changed after" in out["conflicts"][0]["reason"]
    assert (jail / "a.txt").read_text() == "someone else edited this afterwards"
    assert store.undo("t1", "globex", s.undo_handlers())["undone"] == [] and store.ops("t1", "globex") == []


def test_big_files_are_irreversible_and_changes_need_a_journal(jail, store):
    s = files(jail, store, max_checkpoint=4)
    obs = s.observe()
    assert s.classify(Action("delete", "x"), next(e for e in obs.elements if e.name == "a.txt")) == "irreversible"
    bare = FilesSurface(jail)
    obs = bare.observe()
    with pytest.raises(Refused):
        bare.act(Action("delete", ref(obs, "a.txt")), obs.snapshot_id)
    assert (jail / "a.txt").exists()


def test_blob_corruption_is_detected(jail, store):
    s = files(jail, store)
    obs = s.observe()
    s.act(Action("write", ref(obs, "a.txt"), "x"), obs.snapshot_id)
    blob = next(p for p in (store.base / "blobs").rglob("*") if p.is_file())
    blob.write_bytes(b"tampered")
    out = store.undo("t1", "acme", s.undo_handlers())
    assert out["undone"] == [] and out["conflicts"]


def test_compensator_registry_and_irreversible_listing(store):
    seen = []
    compensators.register("crm.note", lambda d: seen.append(d) or "note deleted")
    a = store.append("t9", "acme", "crm.note", "compensatable", {"id": 7})
    store.append("t9", "acme", "mail.send", "irreversible", {"to": "x"})
    out = store.undo("t9", "acme", compensators.handlers())
    assert out["undone"] == [a] and seen == [{"id": 7}] and [n["kind"] for n in out["needs_human"]] == ["mail.send"]


# ── terminal ─────────────────────────────────────────────────────────────────
class FakeRunner:
    def __init__(self):
        self.calls = []

    def run(self, argv, *, cwd, env, timeout, max_output):
        self.calls.append((list(argv), dict(env), timeout, max_output))
        return RunResult(0, "ok " + " ".join(argv))


def test_terminal_allow_list_and_validators(jail, store):
    r = FakeRunner()
    t = TerminalSurface(jail, runner=r, journal=Journal(store, "t2", "acme"))
    obs = t.observe()
    uname = ref(obs, "uname")
    out = t.act(Action("run", uname, "-a"), obs.snapshot_id)
    assert out.ok and r.calls[0][0] == ["uname", "-a"]
    assert set(r.calls[0][1]) == {"PATH", "LANG", "LC_ALL", "HOME"}                # scrubbed environment
    for bad in ["-x", "; rm -rf /", "$(id)", "`id`", "a b c d e", "x\ny", "| cat"]:
        with pytest.raises(Refused):
            t.act(Action("run", uname, bad), obs.snapshot_id)
    with pytest.raises(Refused):
        t.act(Action("run", ref(obs, "ls"), "../.."), obs.snapshot_id)               # path outside the jail
    with pytest.raises(Refused):
        t.act(Action("run", ref(obs, "ls"), "/etc"), obs.snapshot_id)
    assert len(r.calls) == 1                                                       # nothing refused ever reached the runner
    assert argv_for(DEFAULT_ALLOW[6], "-l a.txt", jail) == ["ls", "-l", "a.txt"]
    assert "rm" not in {e.name for e in obs.elements} and "sh" not in {e.name for e in obs.elements}


def test_terminal_non_read_only_is_irreversible_and_journaled(jail, store):
    t = TerminalSurface(jail, allow=[CommandSpec("touch", paths=True, read_only=False)], runner=FakeRunner(),
                        journal=Journal(store, "t3", "acme"))
    obs = t.observe()
    assert t.classify(Action("run", "e1", "x.txt"), obs.elements[0]) == "irreversible"
    t.act(Action("run", "e1", "x.txt"), obs.snapshot_id)
    assert store.undo("t3", "acme", {})["needs_human"][0]["kind"] == "terminal.run"


def test_real_subprocess_runner_is_limited(jail, store):
    t = TerminalSurface(jail, journal=Journal(store, "t4", "acme"))
    obs = t.observe()
    res = t.act(Action("run", ref(obs, "uname"), "-s"), obs.snapshot_id)
    assert res.ok and res.output.strip()


# ── browser / desktop ────────────────────────────────────────────────────────
PAGES = {"https://forms.test/new": {"text": "New hire", "elements": [
    {"role": "textbox", "name": "Full name", "value": ""}, {"role": "textbox", "name": "Password", "secret": True},
    {"role": "link", "name": "elsewhere", "href": "https://evil.test/x"}, {"role": "button", "name": "Submit"}]}}


def browser(store, **kw):
    return BrowserSurface(FakeDriver(PAGES, "https://forms.test/new"), ["forms.test"],
                          journal=Journal(store, "b1", "acme"), resolver=lambda h: ["93.184.216.34"], **kw)


def test_browser_navigation_is_restricted_and_goes_through_the_fetch_gate(store):
    b = browser(store)
    obs = b.observe()
    page = obs.elements[0]
    assert page.role == "page" and host_allowed("https://a.forms.test/x", ["*.forms.test"])
    with pytest.raises(Refused):
        b.act(Action("navigate", page.ref, to="https://evil.test/"), obs.snapshot_id)
    with pytest.raises(Refused):
        b.act(Action("click", ref(obs, "elsewhere")), obs.snapshot_id)                # the link leads off-list
    with pytest.raises(Refused):
        b.act(Action("navigate", page.ref, to="file:///etc/passwd"), obs.snapshot_id)
    private = BrowserSurface(FakeDriver(PAGES, "https://forms.test/new"), ["forms.test"],
                             resolver=lambda h: ["10.0.0.5"])                              # allow-listed name, private address
    o = private.observe()
    with pytest.raises(Refused):
        private.act(Action("navigate", o.elements[0].ref, to="https://forms.test/new"), o.snapshot_id)


def test_browser_classes_secrets_transfers_and_undo(store):
    b = browser(store)
    obs = b.observe()
    name, pw, submit = (next(e for e in obs.elements if e.name == n) for n in ("Full name", "Password", "Submit"))
    assert pw.value is None and b.classify(Action("fill", name.ref, "x"), name) == "undoable"
    with pytest.raises(Refused):
        b.classify(Action("fill", pw.ref, "hunter2"), pw)                                 # never types secrets
    assert b.classify(Action("click", submit.ref), submit) == "irreversible"
    for kind in ("upload", "download"):
        with pytest.raises(Refused):
            b.classify(Action(kind, name.ref), name)
    assert browser(store, allow_transfers=True).classify(Action("upload", "e2"), name) == "irreversible"
    b.act(Action("fill", name.ref, "Asha"), obs.snapshot_id)
    assert b.driver.pages["https://forms.test/new"]["elements"][0]["value"] == "Asha"
    out = store.undo("b1", "acme", b.undo_handlers())
    assert out["undone"] and b.driver.pages["https://forms.test/new"]["elements"][0]["value"] == ""


def test_playwright_is_optional():
    from velaris.control.browser import PlaywrightDriver
    try:
        import playwright  # noqa: F401
    except ImportError:
        with pytest.raises(Refused) as e:
            PlaywrightDriver()
        assert e.value.code == "playwright_missing"


def test_desktop_is_a_documented_stub():
    d = DesktopSurface()
    obs = d.observe()
    assert obs.elements == () and obs.text == "not_configured"
    r = d.act(Action("press", "e1"), obs.snapshot_id)
    assert not r.ok and r.status == "not_configured"
