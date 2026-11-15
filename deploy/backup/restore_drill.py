#!/usr/bin/env python3.11
"""Restore drill for VELARIS_DATA (KAN-51): back it up (or take an archive), restore into a scratch dir, check, time, record.

  restore_drill.py --data /var/lib/velaris            back up the live data first, then drill from that archive
  restore_drill.py --archive FILE.tar.gz              drill from an existing archive (decrypt it first)
  options: --record docs/drills  --note "where this ran"

Checks on the restored copy: every SQLite file passes integrity_check, and the hash-chained trace (trace.jsonl) verifies end
to end with velaris.intel.trace.verify(). Writes restore-<UTC>.json with seconds per step (the measured recovery time).
Exit 0 = pass. The encryption key for personal-data stores is NOT part of the archive; this drill does not touch it.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("velaris_backup", Path(__file__).with_name("velaris_backup.py"))
vb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vb)
sys.path.insert(0, str(ROOT))


def drill(archive: Path) -> dict:
    steps: list = []
    record = {"archive": archive.name, "archive_bytes": archive.stat().st_size, "steps": steps,
              "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    def step(label, fn):
        t0 = time.monotonic()
        try:
            ok, detail = fn()
        except Exception as e:  # a failing step is a failed drill, recorded, not a crash
            ok, detail = False, f"{type(e).__name__}: {str(e)[:200]}"
        steps.append({"step": label, "seconds": round(time.monotonic() - t0, 2), "ok": ok, "detail": detail})
        return ok

    with tempfile.TemporaryDirectory(prefix="velaris-drill-") as tmp:
        target = Path(tmp) / "data"

        def restore():
            vb.restore(archive, target)
            return True, f"{sum(1 for p in target.rglob('*') if p.is_file())} files"

        def sqlite_ok():
            bad = [p.name for p in target.rglob("*") if p.is_file() and vb._is_sqlite(p)
                   and sqlite3.connect(p).execute("PRAGMA integrity_check").fetchone()[0] != "ok"]
            return not bad, f"damaged: {bad}" if bad else "all SQLite files pass integrity_check"

        def trace_ok():
            os.environ["VELARIS_DATA"] = str(target)
            from velaris.intel import trace
            r = trace.verify()
            record["trace_entries"] = r["entries"]
            return r["ok"], f"{r['entries']} entries" + ("" if r["ok"] else f"; broken at {r['broken_at']}: {r['reason']}")

        t_all = time.monotonic()
        if step("restore archive (checksums verified)", restore):
            step("sqlite integrity", sqlite_ok)
            step("trace chain verifies", trace_ok)
        record["total_seconds"] = round(time.monotonic() - t_all, 2)
    record["passed"] = bool(steps) and all(s["ok"] for s in steps)
    return record


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--data", type=Path)
    src.add_argument("--archive", type=Path)
    ap.add_argument("--record", type=Path, default=ROOT / "docs" / "drills")
    ap.add_argument("--note", default="")
    args = ap.parse_args(argv)
    archive = args.archive
    if args.data:
        with tempfile.TemporaryDirectory(prefix="velaris-drill-out-") as out:
            archive = vb.backup(args.data, Path(out))
            return _finish(drill(archive), args)
    if not archive.is_file():
        print(f"no such archive: {archive}", file=sys.stderr)
        return 2
    return _finish(drill(archive), args)


def _finish(rec: dict, args) -> int:
    rec["note"] = args.note
    args.record.mkdir(parents=True, exist_ok=True)
    out = args.record / f"restore-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    out.write_text(json.dumps(rec, indent=2) + "\n")
    for s in rec["steps"]:
        print(f"{'ok  ' if s['ok'] else 'FAIL'} {s['seconds']:>6.2f}s  {s['step']}  {s['detail']}")
    print(f"{'PASS' if rec['passed'] else 'FAIL'}: restored and verified in {rec['total_seconds']}s -> {out}")
    return 0 if rec["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
