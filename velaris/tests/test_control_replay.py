"""Record once, replay without a model, fail closed on drift."""
import copy


from velaris.control.browser import BrowserSurface
from velaris.control.checkpoint import CheckpointStore, Journal
from velaris.control.core import Action
from velaris.control.fake import FakeDriver
from velaris.control.files import FilesSurface
from velaris.control.replay import Program, Recorder, replay

CLOSED = ("drift", "assertion_failed")
URL = "https://forms.test/new"
PAGE = {URL: {"text": "form", "elements": [
    {"role": "textbox", "name": "Full name", "value": ""}, {"role": "textbox", "name": "Email", "value": ""},
    {"role": "button", "name": "Submit"}], "submit_to": "https://forms.test/done"}}


def surface(tmp_path, pages=PAGE, **kw):
    d = FakeDriver(pages, "about:blank", **kw)
    return BrowserSurface(d, ["forms.test"], journal=Journal(CheckpointStore(tmp_path / "cp"), "r1", "acme"),
                          resolver=lambda h: ["93.184.216.34"])


def ref(obs, name):
    return next(e.ref for e in obs.elements if e.name == name)


def record(tmp_path):
    s = surface(tmp_path / "rec")
    rec = Recorder(s, "new-hire-form")
    obs = s.observe()
    rec.act(Action("navigate", obs.elements[0].ref, to=URL), obs.snapshot_id)
    for n, v in (("Full name", "Asha Rao"), ("Email", "asha@acme.test")):
        obs = s.observe()
        rec.act(Action("fill", ref(obs, n), v), obs.snapshot_id)
    obs = s.observe()
    rec.act(Action("submit", ref(obs, "Submit")), obs.snapshot_id)
    return rec.program


def test_recording_replays_model_free_with_parameters(tmp_path):
    prog = record(tmp_path).parametrize({"Asha Rao": "name", "asha@acme.test": "email"})
    prog = Program.from_json(prog.to_json())                                   # stored and loaded again
    s = surface(tmp_path / "play")
    res = replay(prog, s, params={"name": "Ben Ito", "email": "ben@acme.test"}, approved={3: "boss"})
    assert res.status == "completed" and res.done == 4
    assert s.driver.submissions == [{"Full name": "Ben Ito", "Email": "ben@acme.test"}]


def test_the_irreversible_step_stops_the_replay_until_a_named_person_approves(tmp_path):
    prog = record(tmp_path)
    s = surface(tmp_path / "p1")
    res = replay(prog, s)
    assert (res.status, res.step) == ("needs_approval", 3) and s.driver.submissions == []
    assert replay(prog, surface(tmp_path / "p2"), approved={3: "  "}).status == "needs_approval"     # a name is required
    assert replay(prog, surface(tmp_path / "p3"), approved={3: "boss"}).status == "completed"


def test_missing_placeholder_value_stops_the_replay(tmp_path):
    prog = record(tmp_path).parametrize({"Asha Rao": "name"})
    res = replay(prog, surface(tmp_path / "p"), params={})
    assert res.status == "failed" and res.step == 1 and "name" in res.detail


def test_drift_fails_closed(tmp_path):
    prog = record(tmp_path)
    renamed = copy.deepcopy(PAGE)
    renamed[URL]["elements"][1]["name"] = "E-mail address"                    # the site changed a label
    s = surface(tmp_path / "d1", renamed)
    res = replay(prog, s, approved={3: "boss"})
    assert res.status == "assertion_failed" and res.step == 0 and s.driver.submissions == []   # caught right after the navigation
    extra = copy.deepcopy(PAGE)
    extra[URL]["elements"].insert(0, {"role": "button", "name": "Accept cookies"})
    assert replay(prog, surface(tmp_path / "d2", extra), approved={3: "boss"}).status in CLOSED
    dup = copy.deepcopy(PAGE)
    dup[URL]["elements"].append({"role": "textbox", "name": "Email", "value": ""})
    assert replay(prog, surface(tmp_path / "d3", dup), approved={3: "boss"}).status in CLOSED
    assert replay(prog, FilesSurface(tmp_path), approved={}).status == "drift"                # another kind of surface


def test_a_failed_assertion_stops_the_replay(tmp_path):
    prog = record(tmp_path)
    s = surface(tmp_path / "a", unsticky={"Email"})                           # the page ignores what is typed
    res = replay(prog, s, approved={3: "boss"})
    assert res.status == "assertion_failed" and s.driver.submissions == []


def test_policy_denial_stops_a_replay(tmp_path):
    prog = record(tmp_path)
    from velaris.control import policy
    res = replay(prog, surface(tmp_path / "x"), policy_fn=lambda a, o: policy.deny("not this task"), approved={})
    assert (res.status, res.step) == ("denied", 0)


def test_files_recording_replays_on_a_fresh_folder(tmp_path):
    def jail(name):
        d = tmp_path / name
        d.mkdir()
        (d / "a.txt").write_text("x")
        return FilesSurface(d, journal=Journal(CheckpointStore(tmp_path / f"cp-{name}"), name, "acme"))
    src = jail("one")
    rec = Recorder(src, "tidy")
    obs = src.observe()
    rec.act(Action("mkdir", ref(obs, "."), to="txt"), obs.snapshot_id)
    obs = src.observe()
    rec.act(Action("move", ref(obs, "a.txt"), to="txt/a.txt"), obs.snapshot_id)
    dst = jail("two")
    assert replay(rec.program, dst).status == "completed" and (dst.root / "txt" / "a.txt").exists()
    (tmp_path / "three").mkdir()                                              # a folder without a.txt: drift, nothing done
    empty = FilesSurface(tmp_path / "three", journal=Journal(CheckpointStore(tmp_path / "cp3"), "three", "acme"))
    assert replay(rec.program, empty).status == "drift" and not (empty.root / "txt").exists()
