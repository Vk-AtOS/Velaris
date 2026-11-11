"""process_mining.py: directly-follows graph, waits, variants, rework, bottlenecks, conformance."""
import json

import pytest

from velaris.intel import trace
from velaris.intel.process_mining import conformance, discover, from_trace

# (case, activity, ts). c1 and c4 are the happy path, c2 repeats B, c3 goes back from B to A.
LOG = [
    ("c1", "A", 0), ("c1", "B", 10), ("c1", "C", 30),
    ("c2", "A", 0), ("c2", "B", 20), ("c2", "B", 25), ("c2", "C", 65),
    ("c3", "A", 100), ("c3", "B", 104), ("c3", "A", 110), ("c3", "B", 120), ("c3", "C", 130),
    ("c4", "A", 200), ("c4", "B", 210), ("c4", "C", 230),
]


def _events(rows=LOG):
    return [{"case": c, "activity": a, "ts": t} for c, a, t in rows]


@pytest.fixture
def mined():
    return discover(reversed(_events()))        # input order must not matter


def _edge(mined, a, b):
    return next(e for e in mined["edges"] if (e["from"], e["to"]) == (a, b))


def test_traces_are_grouped_and_time_sorted(mined):
    json.dumps(mined)
    assert mined["cases"] == 4 and mined["events"] == 15
    assert mined["traces"]["c3"] == ["A", "B", "A", "B", "C"]
    assert mined["start_activities"] == {"A": 4} and mined["end_activities"] == {"C": 4}


def test_dfg_occurrence_and_case_frequency(mined):
    assert [(e["from"], e["to"], e["count"], e["cases"]) for e in mined["edges"]] == [
        ("A", "B", 5, 4),          # c3 takes A->B twice: 5 occurrences, still only 4 cases
        ("B", "C", 4, 4),
        ("B", "A", 1, 1),
        ("B", "B", 1, 1)]


def test_waiting_time_stats_are_exact(mined):
    assert _edge(mined, "A", "B")["wait"] == {"count": 5, "mean": 10.8, "median": 10.0, "p95": 20.0, "max": 20.0}
    assert _edge(mined, "B", "C")["wait"] == {"count": 4, "mean": 22.5, "median": 20.0, "p95": 40.0, "max": 40.0}
    assert _edge(mined, "B", "B")["wait"] == {"count": 1, "mean": 5.0, "median": 5.0, "p95": 5.0, "max": 5.0}


def test_p95_is_nearest_rank():
    rows = [("c", "A", 0)] + [("c", "A", t) for t in range(1, 41)]      # 40 waits of 1s ...
    rows.append(("c", "A", 140))                                        # ... then 100s
    rows.append(("c", "A", 340))                                        # ... then 200s
    wait = discover(_events(rows))["edges"][0]["wait"]
    assert (wait["count"], wait["p95"], wait["max"]) == (42, 1.0, 200.0)  # rank ceil(39.9) = 40


def test_variants_and_coverage(mined):
    assert mined["variants"] == [
        {"activities": ["A", "B", "C"], "cases": 2, "coverage_pct": 50.0},
        {"activities": ["A", "B", "A", "B", "C"], "cases": 1, "coverage_pct": 25.0},
        {"activities": ["A", "B", "B", "C"], "cases": 1, "coverage_pct": 25.0}]


def test_rework(mined):
    assert mined["rework"] == {
        "activities": [{"activity": "B", "cases": 2}, {"activity": "A", "cases": 1}],
        "self_loops": [{"activity": "B", "count": 1}],
        "short_loops": [{"a": "A", "b": "B", "count": 1}, {"a": "B", "b": "A", "count": 1}]}


def test_bottlenecks_ranked_by_median_wait_times_frequency(mined):
    assert mined["bottlenecks"] == [
        {"from": "B", "to": "C", "median_wait": 20.0, "count": 4, "score": 80.0},
        {"from": "A", "to": "B", "median_wait": 10.0, "count": 5, "score": 50.0},
        {"from": "B", "to": "A", "median_wait": 6.0, "count": 1, "score": 6.0},
        {"from": "B", "to": "B", "median_wait": 5.0, "count": 1, "score": 5.0}]
    top = discover(_events(), top_n=1)["bottlenecks"]
    assert [(b["from"], b["to"]) for b in top] == [("B", "C")]


def test_iso_timestamps_and_bad_timestamps():
    mined = discover([{"case": 1, "activity": "B", "ts": "2026-01-01T00:00:10+00:00"},
                      {"case": 1, "activity": "A", "ts": "2026-01-01T00:00:00Z"},
                      {"case": 1, "activity": "C", "ts": "2026-01-01T00:01:10"}])
    assert mined["traces"] == {"1": ["A", "B", "C"]}
    assert [e["wait"]["max"] for e in mined["edges"]] == [10.0, 60.0]
    with pytest.raises(ValueError):
        discover([{"case": 1, "activity": "A", "ts": None}])


def test_conformance_shadow_dead_and_fitness(mined):
    result = conformance(mined, {("A", "B"), ("B", "C"), ("C", "D")})
    assert result["shadow"] == [{"from": "B", "to": "A", "count": 1}, {"from": "B", "to": "B", "count": 1}]
    assert result["dead"] == [{"from": "C", "to": "D"}]
    assert result["fitness"] == pytest.approx(9 / 11)
    assert conformance(discover([]), [["A", "B"]]) == {
        "shadow": [], "dead": [{"from": "A", "to": "B"}], "fitness": None}


def test_from_trace_mines_the_platform_trace(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    trace.append("agent", "plan", {"run_id": "r1"})
    trace.append("tool", "search", {"run_id": "r1", "query": "x"})
    trace.append("guard", "scan", {"level": "none"})                  # no run_id: skipped
    trace.append("agent", "plan", {"run_id": "r2"})
    trace.append("agent", "answer", {"run_id": "r1"})
    assert trace.verify()["ok"]

    events = from_trace(case_key="run_id")
    assert [(e["case"], e["activity"], e["actor"]) for e in events] == [
        ("r1", "agent.plan", "agent"), ("r1", "tool.search", "tool"),
        ("r2", "agent.plan", "agent"), ("r1", "agent.answer", "agent")]
    mined = discover(events)
    assert mined["traces"] == {"r1": ["agent.plan", "tool.search", "agent.answer"], "r2": ["agent.plan"]}
    assert mined["start_activities"] == {"agent.plan": 2}
    assert conformance(mined, [("agent.plan", "tool.search")])["shadow"] == [
        {"from": "tool.search", "to": "agent.answer", "count": 1}]
    assert from_trace(case_key="thread_id") == []
