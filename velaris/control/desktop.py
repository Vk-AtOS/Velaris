"""Desktop surface: macOS accessibility (AX). A documented stub; nothing is automated here.

What a real one would be: observe() walks the AX tree of the front window (role, title, value,
element path) and assigns refs exactly like the other surfaces; act() presses a ref, sets a
value or sends a menu command, only after the same snapshot check; click-by-coordinates would be
classed irreversible. It needs the Accessibility permission, an app allow-list and a VM or
dedicated user session. None of that exists yet, so every call answers `not_configured`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from velaris.control.core import Action, ActResult, Element, Observation, Refused, Surface


class DesktopSurface(Surface):
    kind = "desktop"

    def _raw(self) -> Tuple[List[Dict[str, Any]], str, str]:
        return [], "not_configured", "desktop:not_configured"

    def act(self, action: Action, snapshot_id: Any) -> ActResult:
        return ActResult(False, "not_configured", status="not_configured")

    def classify(self, action: Action, el: Element) -> str:
        raise Refused("not_configured", "desktop control is not set up")

    def _do(self, action: Action, el: Element, obs: Observation) -> ActResult:
        return ActResult(False, "not_configured", status="not_configured")
