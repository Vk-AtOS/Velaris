"""Test doubles for the control layer: a scripted model, a fake runner and document sink, a fake form site,
and `env()`, a ControlService wired to them with no network and no real commands. Used by the test suite."""
from __future__ import annotations

import hashlib
import json
import re

from velaris.control.checkpoint import CheckpointStore
from velaris.control.fake import FakeDriver
from velaris.control.service import ControlService
from velaris.control.terminal import RunResult
from velaris.intel.llm import FakeLLM

FINAL = json.dumps({"final": "All done! Everything worked."})


def snap(prompt):
    return re.findall(r"CURRENT SNAPSHOT_ID: (\w+)", prompt)[-1]


def refs(prompt):
    block = prompt.rsplit("BEGIN DATA-", 1)[1]
    found = {m.group(3): m.group(1) for m in re.finditer(r'\[(e\d+)\] (\w+) "([^"]*)"', block)}
    found.update({"<withheld>": m.group(1) for m in re.finditer(r"\[(e\d+)\] \w+ <withheld", block)})
    return found


def step(kind, name, value=None, to=None, snapshot=None):
    return (kind, name, value, to, snapshot)


def model(*steps):
    """A scripted model: each step is (action, element name, value, to, snapshot override) or a raw reply."""
    it = iter(steps)

    def reply(prompt, _model):
        s = next(it, None)
        if s is None:
            return FINAL
        if isinstance(s, str):
            return s
        kind, name, value, to, snapshot = s
        args = {"action": kind, "ref": refs(prompt).get(name, "e99"), "snapshot_id": snapshot or snap(prompt)}
        if snapshot == "MISSING":
            del args["snapshot_id"]
        args.update({k: v for k, v in (("value", value), ("to", to)) if v is not None})
        return json.dumps({"tool": "act", "args": args})
    return reply


class FakeRunner:
    def __init__(self, fail=()):
        self.calls, self.fail = [], set(fail)

    def run(self, argv, *, cwd, env, timeout, max_output):
        self.calls.append(list(argv))
        return RunResult(1 if argv[0] in self.fail else 0, "ran " + " ".join(argv))


class FakeSink:
    def __init__(self):
        self.docs = {}

    def ingest(self, name, data):
        action = "UPDATED" if name in self.docs else "ADDED"
        self.docs[name] = hashlib.sha256(data).hexdigest()
        return {"action": action}

    def remove(self, name):
        return self.docs.pop(name, None) is not None

    def documents(self):
        return [{"name": n, "sha256": h} for n, h in self.docs.items()]


FORM = "https://forms.test/new"
PAGE = {FORM: {"text": "New hire form", "elements": [
    {"role": "textbox", "name": "Full name", "value": ""}, {"role": "textbox", "name": "Email", "value": ""},
    {"role": "button", "name": "Submit"}], "submit_to": "https://forms.test/done"}}


class Env:
    def __init__(self, tmp_path, monkeypatch, replies=(), gate=None, **kw):
        monkeypatch.setenv("VELARIS_ORG", "acme")
        self.ws, self.runner, self.sink = tmp_path / "ws", FakeRunner(), FakeSink()
        self.driver = FakeDriver(PAGE, "about:blank", **kw)
        (self.ws / "acme").mkdir(parents=True)
        self.llm = FakeLLM(model(*replies))
        self.svc = ControlService(store=CheckpointStore(tmp_path / "cp"), llm=self.llm, gate=gate, workspace=self.ws,
                                  runner=self.runner, driver_factory=lambda: self.driver, flow_path=str(tmp_path / "flow.db"),
                                  sink_factory=lambda c: self.sink, resolver=lambda h: ["93.184.216.34"])

    @property
    def home(self):
        return self.ws / "acme"

    def inbox(self, **files):
        d = self.home / "inbox"
        d.mkdir(exist_ok=True)
        for n, c in files.items():
            (d / n.replace("__", ".")).write_bytes(c if isinstance(c, bytes) else c.encode())
        return d

    def tree(self, d):
        return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


def env(tmp_path, monkeypatch, *replies, **kw):
    return Env(tmp_path, monkeypatch, replies, **kw)
