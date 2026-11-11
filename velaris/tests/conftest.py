"""
Test bootstrap.

Puts the repo root on sys.path and maps the two obsolete package roots that
older tests still import (`agents.X`, `live.agents.X`) onto velaris.agents,
which resolves agents from departments/.
"""
import os
import sys
import types

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import velaris.agents  # noqa: E402  (needs ROOT on sys.path first)

sys.modules.setdefault("agents", velaris.agents)
_live = sys.modules.setdefault("live", types.ModuleType("live"))
_live.__path__ = []
_live.agents = velaris.agents
sys.modules.setdefault("live.agents", velaris.agents)
