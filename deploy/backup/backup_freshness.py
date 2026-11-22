#!/usr/bin/env python3.11
"""Alert when the newest GOOD Velaris backup is older than 26 h (VEL-32). Standard library only.

  backup_freshness.py --dir /var/backups/velaris [--max-age-hours 26]

Exit 0 = the newest good backup is fresh. Exit 2 = ALERT (printed to stderr, so journald/cron mail carries it): no backup,
no good backup (partial, corrupt, missing .sha256, bad manifest) or the newest good one is too old. Age comes from the UTC
stamp in the archive name velaris_backup.py writes (velaris-data-YYYYmmddTHHMMSSZ.tar.gz), not from file mtime, which a
copy or restore would reset. "Good" = the .sha256 sidecar matches the archive and the tar opens with a valid MANIFEST.json.
Only the newest archive decides: a bad newest archive is an alert even if an older one is fine (last night's run failed).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Tuple

MANIFEST = "MANIFEST.json"
logger = logging.getLogger("velaris.backup_freshness")
NAME = re.compile(r"^velaris-data-(\d{8}T\d{6}Z)\.tar\.gz$")


def _verify(archive: Path) -> Optional[str]:
    """None if the archive is complete and intact, else the reason it is not."""
    sidecar = Path(str(archive) + ".sha256")
    try:
        if not sidecar.is_file():
            return "missing .sha256 sidecar"
        h = hashlib.sha256()
        with archive.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if sidecar.read_text().split()[0] != h.hexdigest():
            return "checksum does not match the .sha256"
        with tarfile.open(archive, "r:gz") as tar:
            f = tar.extractfile(MANIFEST)
            if f is None or "files" not in json.load(f):
                return "manifest is invalid"
    except Exception as e:  # unreadable, truncated, not a tar, bad json: all mean "not a good backup"
        logger.warning("%s failed verification: %s", archive.name, e)
        return f"unreadable ({type(e).__name__})"
    return None



def check(directory: Path, max_age_hours: float = 26.0, now: Callable[[], float] = time.time) -> Tuple[bool, str]:
    archives = sorted(p for p in directory.glob("velaris-data-*.tar.gz") if NAME.match(p.name)) if directory.is_dir() else []
    if not archives:
        return False, f"ALERT: no Velaris backup found in {directory}"
    newest = archives[-1]
    bad = _verify(newest)
    if bad:
        return False, f"ALERT: newest backup {newest.name} is not good: {bad}"
    stamp = datetime.strptime(NAME.match(newest.name).group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    age_h = (now() - stamp.timestamp()) / 3600
    if age_h > max_age_hours:
        return False, f"ALERT: last good backup {newest.name} is {age_h:.1f} h old (limit {max_age_hours:g} h)"
    return True, f"OK: last good backup {newest.name} is {age_h:.1f} h old (limit {max_age_hours:g} h)"


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--dir", type=Path, default=Path("/var/backups/velaris"))
    p.add_argument("--max-age-hours", type=float, default=26.0)
    a = p.parse_args(argv)
    ok, msg = check(a.dir, a.max_age_hours)
    print(msg, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
