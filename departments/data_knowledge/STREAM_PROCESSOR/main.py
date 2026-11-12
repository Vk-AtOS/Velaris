"""STREAM_PROCESSOR: tumbling-window aggregation over event streams.

define() declares a stream: the window length, which field holds the number to
aggregate, and optionally a field to group by. ingest() takes batches of events
({"ts": seconds, <value_field>: number, ...}) in any order and keeps, per window
and group, the count, sum, minimum and maximum.

Event time, not arrival time, decides the window: [start, start + window_s),
start = floor(ts / window_s) * window_s. The watermark is the largest timestamp
seen minus `lateness_s`; a window is closed once it ends at or before the
watermark, and an event for a closed window is counted as late and dropped, so
a closed window's result never changes. Aggregates survive restarts.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from velaris.agentkit.infra_store import State, fail, invalid, is_name, is_number, ok

NAME = "STREAM_PROCESSOR"
MAX_BATCH = 10000
MAX_WINDOWS = 5000


class STREAM_PROCESSORAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = State(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def define(self, stream: str, window_s: float, value_field: str, key_field: Optional[str] = None,
               lateness_s: float = 0.0) -> Dict[str, Any]:
        if not is_name(stream) or not is_number(window_s, 0.001) or not is_number(lateness_s, 0):
            return invalid("need a stream name, window_s > 0 and lateness_s >= 0")
        if not (isinstance(value_field, str) and value_field) or not (key_field is None or (isinstance(key_field, str) and key_field)):
            return invalid("value_field (and key_field, if given) must be field names")
        spec = {"window_s": window_s, "value_field": value_field, "key_field": key_field, "lateness_s": lateness_s}

        def put(data: Dict[str, Any]) -> Dict[str, Any]:
            streams = data.setdefault("streams", {})
            if stream in streams and streams[stream]["spec"] != spec:
                return fail("exists", "stream is already defined differently; its windows would not be comparable")
            streams.setdefault(stream, {"spec": spec, "max_ts": None, "windows": {}, "late": 0, "invalid": 0})
            return ok(stream=stream, **spec)
        return self._state.change(put)

    def ingest(self, stream: str, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(events, list) or len(events) > MAX_BATCH:
            return invalid(f"events must be a list of at most {MAX_BATCH}")

        def take(data: Dict[str, Any]) -> Dict[str, Any]:
            st = data.get("streams", {}).get(stream) if isinstance(stream, str) else None
            if st is None:
                return fail("unknown_stream", "define() has not been called for this stream")
            spec, accepted, late, bad = st["spec"], 0, 0, 0
            for ev in events:
                value = ev.get(spec["value_field"]) if isinstance(ev, dict) else None
                key = ev.get(spec["key_field"]) if isinstance(ev, dict) and spec["key_field"] else ""
                if not isinstance(ev, dict) or not is_number(ev.get("ts"), 0) or not is_number(value) or not isinstance(key, str):
                    bad += 1
                    continue
                start = math.floor(ev["ts"] / spec["window_s"]) * spec["window_s"]
                watermark = -math.inf if st["max_ts"] is None else st["max_ts"] - spec["lateness_s"]
                if start + spec["window_s"] <= watermark:
                    late += 1
                    continue
                w = st["windows"].setdefault(f"{start}|{key}", {"start": start, "key": key, "count": 0, "sum": 0.0,
                                                                "min": value, "max": value})
                w.update(count=w["count"] + 1, sum=w["sum"] + value, min=min(w["min"], value), max=max(w["max"], value))
                st["max_ts"] = ev["ts"] if st["max_ts"] is None else max(st["max_ts"], ev["ts"])
                accepted += 1
            st["late"], st["invalid"] = st["late"] + late, st["invalid"] + bad
            for old in sorted(st["windows"], key=lambda k: st["windows"][k]["start"])[:max(0, len(st["windows"]) - MAX_WINDOWS)]:
                del st["windows"][old]
            return ok(accepted=accepted, late=late, invalid=bad)
        return self._state.change(take)

    def results(self, stream: str, closed_only: bool = True) -> Dict[str, Any]:
        """Window aggregates in time order; by default only closed windows, whose values are final."""
        st = self._state.load().get("streams", {}).get(stream) if isinstance(stream, str) else None
        if st is None:
            return fail("unknown_stream", "no such stream")
        spec = st["spec"]
        watermark = None if st["max_ts"] is None else st["max_ts"] - spec["lateness_s"]
        out = []
        for w in sorted(st["windows"].values(), key=lambda w: (w["start"], w["key"])):
            closed = watermark is not None and w["start"] + spec["window_s"] <= watermark
            if closed or not closed_only:
                out.append({**w, "end": w["start"] + spec["window_s"], "avg": round(w["sum"] / w["count"], 6),
                            "closed": closed})
        return ok(stream=stream, windows=out, watermark=watermark, late=st["late"], invalid=st["invalid"])
