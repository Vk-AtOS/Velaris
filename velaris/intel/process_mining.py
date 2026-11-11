"""Discover how work actually flows, from an event log.

An event is {case, activity, ts, actor?}: something happened (activity) to one
unit of work (case) at a time (ts, seconds as a number or an ISO-8601 string).

  1. from_trace()   the platform's own hash-chained trace is already an event
                    log: case = a payload field such as "run_id", activity =
                    "actor.action". So the platform can mine its own behaviour.
  2. discover()     group by case, sort by time, then one pass per case builds
                    the directly-follows graph (how often b came straight after
                    a), waiting times per edge, start/end activities, variants,
                    rework and a bottleneck ranking.
  3. conformance()  compare the mined edges with a designed process: shadow
                    edges happen but were never designed, dead edges were
                    designed but never happen.

Pure functions, no model, no network.
Complexity ceiling: O(n log n) time for n events (the per-case sort and the
per-edge sort for median/p95; everything else is a single pass) and O(n) memory
(every waiting time is kept). Switch to streaming quantile sketches if a log
no longer fits in memory.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import fmean, median
from typing import Any, Dict, Iterable, List, Optional, Tuple

from velaris.intel import trace


def from_trace(case_key: str = "run_id") -> List[Dict[str, Any]]:
    """Events from the platform trace. Entries whose payload lacks `case_key` are skipped."""
    events = []
    for e in trace.entries():
        case = e["payload"].get(case_key)
        if case is not None:
            events.append({"case": str(case), "activity": f"{e['actor']}.{e['action']}",
                           "ts": e["ts"], "actor": e["actor"]})
    return events


def _seconds(ts: Any) -> float:
    if isinstance(ts, (int, float)) and not isinstance(ts, bool):
        return float(ts)
    if isinstance(ts, str):
        moment = datetime.fromisoformat(ts)
        if moment.tzinfo is None:        # a bare timestamp is read as UTC
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.timestamp()
    raise ValueError(f"unsupported timestamp: {ts!r}")


def _wait_stats(waits: List[float]) -> Dict[str, float]:
    ordered = sorted(waits)
    n = len(ordered)
    return {"count": n, "mean": fmean(ordered), "median": median(ordered),
            "p95": ordered[(95 * n + 99) // 100 - 1],      # nearest rank: ceil(0.95 n)
            "max": ordered[-1]}


def discover(events: Iterable[Dict[str, Any]], top_n: int = 5) -> Dict[str, Any]:
    """Mine an event log. Events may arrive in any order; ties in time keep input order."""
    by_case: Dict[str, List[Tuple[float, int, str]]] = defaultdict(list)
    for i, e in enumerate(events):
        by_case[str(e["case"])].append((_seconds(e["ts"]), i, str(e["activity"])))

    traces: Dict[str, List[str]] = {}
    occurrences: Counter = Counter()        # every time b directly followed a
    case_frequency: Counter = Counter()     # number of cases in which it happened at least once
    waits: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    starts: Counter = Counter()
    ends: Counter = Counter()
    variants: Counter = Counter()
    rework_cases: Counter = Counter()
    short_loops: Counter = Counter()        # (a, b) for each a-b-a
    for case, rows in by_case.items():
        rows.sort()
        acts = [activity for _, _, activity in rows]
        traces[case] = acts
        starts[acts[0]] += 1
        ends[acts[-1]] += 1
        variants[tuple(acts)] += 1
        rework_cases.update(a for a, count in Counter(acts).items() if count > 1)
        pairs = list(zip(acts, acts[1:]))
        occurrences.update(pairs)
        case_frequency.update(set(pairs))
        for i, pair in enumerate(pairs):
            waits[pair].append(rows[i + 1][0] - rows[i][0])
        short_loops.update((a, b) for a, b, c in zip(acts, acts[1:], acts[2:]) if a == c != b)

    edges = [{"from": a, "to": b, "count": count, "cases": case_frequency[(a, b)],
              "wait": _wait_stats(waits[(a, b)])}
             for (a, b), count in sorted(occurrences.items(), key=lambda kv: (-kv[1], kv[0]))]
    ranked = sorted(edges, key=lambda e: (-e["wait"]["median"] * e["count"], e["from"], e["to"]))
    return {
        "cases": len(traces),
        "events": sum(len(acts) for acts in traces.values()),
        "traces": traces,
        "edges": edges,
        "start_activities": dict(starts.most_common()),
        "end_activities": dict(ends.most_common()),
        "variants": [{"activities": list(seq), "cases": count,
                      "coverage_pct": round(100 * count / len(traces), 2)}
                     for seq, count in sorted(variants.items(), key=lambda kv: (-kv[1], kv[0]))],
        "rework": {
            "activities": [{"activity": a, "cases": count}
                           for a, count in sorted(rework_cases.items(), key=lambda kv: (-kv[1], kv[0]))],
            "self_loops": [{"activity": a, "count": count}
                           for (a, b), count in sorted(occurrences.items()) if a == b],
            "short_loops": [{"a": a, "b": b, "count": count}
                            for (a, b), count in sorted(short_loops.items())],
        },
        "bottlenecks": [{"from": e["from"], "to": e["to"], "median_wait": e["wait"]["median"],
                         "count": e["count"], "score": e["wait"]["median"] * e["count"]}
                        for e in ranked[:top_n]],
    }


def conformance(discovered: Dict[str, Any],
                expected_edges: Iterable[Tuple[str, str]]) -> Dict[str, Any]:
    """Compare mined edges with a designed process (a set of (from, to) pairs).

    fitness = share of observed transitions that follow a designed edge; None when
    nothing was observed, because an empty log proves nothing either way.
    """
    observed = {(e["from"], e["to"]): e["count"] for e in discovered["edges"]}
    expected = {tuple(edge) for edge in expected_edges}
    total = sum(observed.values())
    designed = sum(count for edge, count in observed.items() if edge in expected)
    fitness: Optional[float] = designed / total if total else None
    return {
        "shadow": [{"from": a, "to": b, "count": observed[(a, b)]}
                   for a, b in sorted(observed.keys() - expected)],
        "dead": [{"from": a, "to": b} for a, b in sorted(expected - observed.keys())],
        "fitness": fitness,
    }
