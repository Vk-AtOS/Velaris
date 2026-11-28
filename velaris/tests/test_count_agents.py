"""VEL-80: the agent counts in README.md come from tools/count_agents.py, not from memory, and stay consistent."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _script():
    spec = importlib.util.spec_from_file_location("count_agents", ROOT / "tools" / "count_agents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_readme_contains_the_table_the_script_prints():
    s = _script()
    table = s.markdown(s.count())
    assert table in (ROOT / "README.md").read_text(encoding="utf-8"), "README.md agent table is stale: run tools/count_agents.py --markdown"


def test_counts_are_consistent_with_each_other():
    c = _script().count()
    assert sum(c["static"].values()) == c["agents"] == 346
    assert c["model_in_file"] <= c["model_reach"] <= c["agents"]
    assert c["real_model_ready"] <= c["agents"]


def test_no_real_model_score_is_committed_as_ready_without_a_real_model_file():
    # evals/scores holds only the offline fake-oracle run unless a real model was run and committed.
    scores = sorted(p.name for p in (ROOT / "evals" / "scores").glob("*.json"))
    if all(name.startswith("fake") for name in scores):
        assert _script().count()["real_model_ready"] == 0
