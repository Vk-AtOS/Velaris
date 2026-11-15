"""Give legacy rows the deployment's organisation (KAN-68):  python3.11 -m velaris.core.backfill_org [--apply]

Rows written before tenancy (VELARIS_ORG, commit 5720f3d) carry no organisation and are invisible or held. This sets
the configured organisation on them: leave requests (LEAVE_MANAGEMENT), ITSM tickets, recruitment candidates and
onboarding employees, performance rows. Default is a dry run that only reports; --apply writes. Idempotent (only rows
without an organisation are touched, a second run changes nothing); mixed data keeps the rows that already name an
organisation, including other organisations'. Refuses when VELARIS_ORG is unset. Take a backup first
(deploy/backup/velaris_backup.py): the update is one transaction per store, but there is no undo.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from velaris.agentkit.state import JsonState, peek_dir
from velaris.core.access import deployment_org
from velaris.core.sealed_sqlite import connect_sealed

SQLITE_TABLES = [("LEAVE_MANAGEMENT", "leaves.db", "leave_requests"), ("RECRUITMENT_ATS", "recruitment.db", "candidates"),
                 ("EMPLOYEE_ONBOARDING", "employee_onboarding.db", "employees"),
                 ("PERFORMANCE_REVIEW_ENGINE", "reviews.db", "okrs"), ("PERFORMANCE_REVIEW_ENGINE", "reviews.db", "reviews"),
                 ("PERFORMANCE_REVIEW_ENGINE", "reviews.db", "calibration")]


class BackfillError(RuntimeError):
    pass


def _sqlite(agent: str, filename: str, table: str, org: str, apply: bool) -> Optional[Dict[str, int]]:
    path = peek_dir(agent) / filename
    if not path.exists():
        return None
    conn = connect_sealed(path, f"hr:{agent}")      # the HR stores are sealed at rest
    try:
        if "org" not in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}:
            return None                                   # table (or the column) was never created: nothing to fill
        where = "org IS NULL OR TRIM(org)=''"
        found = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
        if apply and found:
            with conn:
                conn.execute(f"UPDATE {table} SET org=? WHERE {where}", (org,))
        return {"found": found, "updated": found if apply else 0}
    finally:
        conn.close()


def _tickets(org: str, apply: bool) -> Optional[Dict[str, int]]:
    st = JsonState("ITSM_ENGINE", "tickets.json")
    if not st.path.exists():
        return None
    out = {"found": 0, "updated": 0}

    def fill(data: Dict[str, Any]) -> None:
        for t in data.get("tickets", {}).values():
            if isinstance(t, dict) and not str(t.get("org") or "").strip():
                out["found"] += 1
                if apply:
                    t["org"] = org
                    out["updated"] += 1
    if apply:
        st.update(fill)
    else:
        fill(st.load())                                  # dry run: look, never save
    return out


def backfill(apply: bool = False, org: Optional[str] = None) -> Dict[str, Any]:
    org = (org or deployment_org() or "").strip()
    if not org:
        raise BackfillError("VELARIS_ORG is not set: refusing to guess which organisation the legacy rows belong to")
    report: Dict[str, Any] = {"org": org, "dry_run": not apply, "stores": {}}
    for agent, filename, table in SQLITE_TABLES:
        if (r := _sqlite(agent, filename, table, org, apply)) is not None:
            report["stores"][f"{agent}.{table}"] = r
    if (r := _tickets(org, apply)) is not None:
        report["stores"]["ITSM_ENGINE.tickets"] = r
    report["total_found"] = sum(s["found"] for s in report["stores"].values())
    report["total_updated"] = sum(s["updated"] for s in report["stores"].values())
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python3.11 -m velaris.core.backfill_org", description=__doc__.splitlines()[0])
    p.add_argument("--apply", action="store_true", help="write the changes (default: dry run, report only)")
    a = p.parse_args(argv)
    try:
        print(json.dumps(backfill(apply=a.apply), indent=2))
    except BackfillError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
