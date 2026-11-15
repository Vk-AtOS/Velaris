"""KAN-54: the committed agent pages match the code, and the drift comparison finds what an outside page lacks."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("gen_agent_docs", ROOT / "tools" / "gen_agent_docs.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def test_committed_agent_pages_are_current():
    pages, _ = gen.build()
    assert gen.stale(pages) == [], "run `python3.11 tools/gen_agent_docs.py` and commit docs/agents"


def test_drift_reports_missing_page_method_state_and_dependency():
    facts = {"A": {"methods": ["run", "stop"], "state": ["state.json"], "deps": ["velaris.intel.llm"]},
             "B": {"methods": ["go"], "state": [], "deps": []},
             "C": {"methods": ["x"], "state": [], "deps": []}}
    exported = {"A": "Calls run() and keeps nothing.", "B": "go is documented", "C": None}
    assert gen.drift(facts, exported) == {
        "A": ["method stop", "state file state.json", "dependency velaris.intel.llm"], "C": ["no page"]}


def test_stale_flags_a_changed_or_missing_page():
    pages, _ = gen.build()
    first = sorted(pages)[0]
    assert gen.stale({**pages, first: pages[first] + "\nedited"}) == [first]
    assert gen.stale({**pages, "nowhere/NEW.md": "x"}) == ["nowhere/NEW.md"]
