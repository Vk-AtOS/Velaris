"""The shared agentkit modules (results, checks, state, conditions, graph): behaviour every agent family relies on."""
import os
import stat


from velaris.agentkit import checks, conditions, graph, results
from velaris.agentkit.state import JsonState, append_line, peek_dir, read_lines


def test_results_and_checks():
    assert results.ok(a=1) == {"status": "ok", "a": 1}
    assert results.invalid("x")["status"] == "invalid_input" and results.health("A")["agent"] == "A"
    assert checks.number(True) is None and checks.number("5") is None and checks.number(float("nan")) is None
    assert checks.number(5, 0, 10) == 5.0 and checks.number(11, 0, 10) is None
    assert checks.ident("  a ") == "a" and checks.ident(" ") is None and checks.is_name("a/b") is False


def test_state_reads_create_nothing_and_saves_are_private(tmp_path):
    s = JsonState("AGENT_X", "s.json", {"n": 0})
    assert s.load() == {"n": 0} and not peek_dir("AGENT_X").exists()
    s.update(lambda d: d.__setitem__("n", 1))
    assert JsonState("AGENT_X", "s.json").load() == {"n": 1}
    assert stat.S_IMODE(os.stat(peek_dir("AGENT_X") / "s.json").st_mode) == 0o600


def test_state_follows_velaris_data_and_sets_corrupt_files_aside(tmp_path, monkeypatch):
    s = JsonState("AGENT_Y", "s.json", {"n": 0})
    s.save({"n": 5})
    home = os.environ["VELARIS_DATA"]
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path / "other"))
    assert s.load() == {"n": 0}                                   # resolved per call, not cached at import
    monkeypatch.setenv("VELARIS_DATA", home)
    path = peek_dir("AGENT_Y") / "s.json"
    path.write_text("{ not json")
    assert s.load() == {"n": 0} and [p.name for p in path.parent.iterdir() if "corrupt" in p.name]


def test_json_lines_skip_torn_last_line(tmp_path):
    p = tmp_path / "q.jsonl"
    append_line(p, {"a": 1})
    p.write_text(p.read_text() + '{"b"')
    assert read_lines(p) == [{"a": 1}]


def test_graph_order_reports_cycles_and_unknown_dependencies():
    out = graph.order({"a": [], "b": ["a"], "c": ["b", "zz"], "x": ["y"], "y": ["x"]})
    assert out["order"] == ["a", "b", "c"] and out["missing"] == {"c": ["zz"]}
    assert out["unordered"] == ["x", "y"] and out["cycle"][0] == out["cycle"][-1]


def test_compare_is_three_valued():
    assert conditions.compare("gt", 5, 1) is True and conditions.compare("gt", "5", 1) is None
    assert conditions.compare("eq", 1, True) is None and conditions.compare("eq", True, True) is True
    assert conditions.compare("contains", [1, 2], 2) is True and conditions.compare("contains", 5, 2) is None
    assert conditions.compare("gt", conditions.MISSING, 1) is None
    assert conditions.resolve(None, "deny") is True and conditions.resolve(None) is False


def test_a_number_too_large_for_a_float_cannot_be_evaluated_and_never_raises():
    """A huge int in a request must make a deny rule hold (cannot evaluate), not raise out of the policy check."""
    from decimal import Decimal
    from velaris.agentkit import conditions
    huge = 10 ** 400
    for value in (huge, -huge, Decimal("1e999")):
        assert conditions._kind(value) is None
