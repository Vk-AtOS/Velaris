"""
velaris.agents — agent package.

Agent folders live in departments/<department>/<AGENT>/main.py. Every
department directory is added to this package's search path, so each agent
is importable as velaris.agents.<AGENT>.main (agent names are unique across
departments) regardless of which department it sits in.
"""
from pathlib import Path

DEPARTMENTS_DIR = Path(__file__).resolve().parents[2] / "departments"


def department_dirs():
    """Department directories (including _ai_core and _connectors), sorted."""
    if not DEPARTMENTS_DIR.is_dir():
        return []
    return sorted(
        d for d in DEPARTMENTS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith((".", "__"))
    )


__path__ = list(__path__) + [str(d) for d in department_dirs()]
