"""KAN-189: the numbers the README states are the numbers the code produces, and no doc names a directory that does not exist."""
import re
from pathlib import Path

from velaris.agents.inventory import classify
from velaris.agents import department_dirs

ROOT = Path(__file__).resolve().parents[2]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _agents():
    return [m for d in department_dirs() for m in sorted(Path(d).glob("*/main.py"))]


def test_readme_agent_counts_match_the_inventory():
    agents = _agents()
    counts = {k: 0 for k in ("real", "rule_based", "not_implemented")}
    for f in agents:
        counts[classify(f.read_text(errors="replace"))] += 1
    row = re.search(r"\| all departments \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|", README)
    assert row, "README must keep the 'all departments' row"
    assert tuple(map(int, row.groups())) == (counts["real"], counts["rule_based"], counts["not_implemented"], len(agents))
    assert f"{len(agents)} in {len(department_dirs())} departments" in README


def test_readme_names_only_paths_that_exist():
    for path in re.findall(r"`((?:departments|velaris|deploy|docs|tools)/[A-Za-z0-9_./-]*)`", README):
        clean = path.split("<")[0].rstrip("/")
        assert (ROOT / clean).exists(), f"README names {path}, which does not exist"


def test_inventory_counts_state_kept_through_jsonstate_as_real():
    """KAN-63: an agent whose state lives in files under VELARIS_DATA (JsonState, directly or through an agentkit helper)
    is `real`, not `rule_based`. Before, only open()/sqlite3-style calls counted."""
    direct = "from velaris.agentkit.state import JsonState\nclass A:\n    def f(self, x):\n        return x + 1 if x else 0\n"
    helper = "from velaris.agentkit.hiring_common import Store\nclass A:\n    def f(self, x):\n        return x + 1 if x else 0\n"
    plain = "class A:\n    def f(self, x):\n        return x + 1 if x else 0\n"
    assert classify(direct) == "real" and classify(helper) == "real" and classify(plain) == "rule_based"
