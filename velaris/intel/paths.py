"""Where the intelligence core keeps its files."""
from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    """VELARIS_DATA if set, else ~/.velaris. Created on first use."""
    d = Path(os.environ.get("VELARIS_DATA") or Path.home() / ".velaris")
    d.mkdir(parents=True, exist_ok=True)
    return d


def agent_dir(name: str) -> Path:
    """Private state directory for one department agent: <data_dir>/agents/<name>.

    Agents keep signing keys and logs here, so it is owner-only.
    """
    d = data_dir() / "agents" / name
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d
