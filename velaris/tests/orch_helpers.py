"""A small fake agent engine for the orchestration tests: real registry, real allowlist rules, real Flow."""
import json

from velaris.api import allowlist
from velaris.api.allowlist import ACT, READ, Rule
from velaris.core.access import Caller
from velaris.intel import providers, tools
from velaris.orchestration import autonomy, identity


class DemoAgent:
    """Demo agent."""
    calls = []

    def lookup(self, q: str) -> dict:
        """Look something up."""
        DemoAgent.calls.append(("lookup", q))
        if q == "boom":
            raise ValueError("internal detail that must not reach the model")
        return {"answer": q.upper()}

    def file_note(self, text: str) -> dict:
        """File a note."""
        DemoAgent.calls.append(("file_note", text))
        return {"filed": text}

    def restricted_note(self, text: str) -> dict:
        """File a note only an hr_admin may file."""
        DemoAgent.calls.append(("restricted_note", text))
        return {"filed": text}

    def make_payment(self, amount: float, vendor: str) -> dict:
        """Pay a vendor."""
        DemoAgent.calls.append(("make_payment", amount, vendor))
        return {"paid": amount}

    def erase_all(self) -> dict:
        """Erase everything."""
        DemoAgent.calls.append(("erase_all",))
        return {"erased": True}


class Router:
    def __init__(self, dept):
        self.departments = {"DEMO": dept}
        self.failed = {}


class FakeEngine:
    def __init__(self, dept="finance"):
        self.router = Router(dept)

    def agent_class(self, name):
        if name != "DEMO":
            raise LookupError(name)
        return DemoAgent

    def run(self, agent, method, params, *, caller=None, config=None):
        return getattr(DemoAgent(), method)(**(params or {}))


def install(monkeypatch, dept="finance"):
    """Declare DEMO in the allowlist, register its tools in `dept`, open a model provider. Returns the engine."""
    monkeypatch.setitem(allowlist.METHODS, "DEMO", {
        "lookup": Rule(READ), "file_note": Rule(ACT), "restricted_note": Rule(ACT, roles=frozenset({"hr_admin"})), "make_payment": Rule(ACT), "erase_all": Rule(ACT)})
    monkeypatch.setattr(autonomy, "NOT_FILINGS", autonomy.NOT_FILINGS | {"DEMO.file_note", "DEMO.restricted_note"})
    DIRECTORY.clear()
    DIRECTORY.update({(c.org, c.id): c for c in (STAFF, BOSS)})
    monkeypatch.setattr(identity, "_resolver", lambda org, uid: DIRECTORY.get((org, uid)))     # a note, not a filing
    DemoAgent.calls.clear()
    tools.clear()
    engine = FakeEngine(dept)
    tools.register_allowlist(engine)
    providers.create("fk", kind="ollama", sensitivity_allowed=["public", "internal", "restricted"])
    return engine


def call(tool, **args):
    return json.dumps({"tool": tool, "args": args})


DIRECTORY = {}                 # (org, id) -> the person's CURRENT Caller; absent means inactive
FINAL = json.dumps({"final": "done"})
STAFF = Caller("u1", "acme", frozenset({"employee"}))
BOSS = Caller("boss", "acme", frozenset({"flow_approver", "governance_admin"}))
