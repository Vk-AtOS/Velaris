"""Where the intelligence core keeps its files."""
from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    """VELARIS_DATA if set, else ~/.velaris. Created on first use."""
    d = Path(os.environ.get("VELARIS_DATA") or Path.home() / ".velaris")
    d.mkdir(parents=True, exist_ok=True)
    return d
