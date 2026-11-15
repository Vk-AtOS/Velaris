"""KAN-106: an agent never forces DEBUG level or adds its own console handler; the application decides."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2] / "departments"


def test_no_agent_sets_its_own_log_level_or_handler():
    bad = []
    for f in sorted(ROOT.glob("*/*/*.py")):
        text = f.read_text()
        if re.search(r"\.setLevel\(\s*logging\.DEBUG\s*\)|logging\.StreamHandler\(", text):
            bad.append(str(f.relative_to(ROOT)))
    assert not bad, f"agents that force DEBUG logging or add their own handler: {bad}"
