"""VEL-32: the freshness check alerts on stale, missing, partial or corrupt backups (fake clock, temp dirs)."""
import importlib.util
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "deploy" / "backup"
_s = importlib.util.spec_from_file_location("backup_freshness", ROOT / "backup_freshness.py")
bf = importlib.util.module_from_spec(_s)
_s.loader.exec_module(bf)
_s = importlib.util.spec_from_file_location("velaris_backup", ROOT / "velaris_backup.py")
vb = importlib.util.module_from_spec(_s)
_s.loader.exec_module(vb)

T0 = 1_800_000_000.0  # fake "now"


def stamp(hours_ago: float) -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(T0 - hours_ago * 3600))


def real_backup(tmp: Path, hours_ago: float) -> Path:
    data = tmp / "data"
    data.mkdir(exist_ok=True)
    (data / "trace.jsonl").write_text('{"n":1}\n')
    out = tmp / "out"
    a = vb.backup(data, out)
    new = out / f"velaris-data-{stamp(hours_ago)}.tar.gz"
    a.rename(new)
    Path(str(a) + ".sha256").rename(Path(str(new) + ".sha256"))
    Path(str(new) + ".sha256").write_text(Path(str(new) + ".sha256").read_text().split()[0] + f"  {new.name}\n")
    return new


def run(tmp):
    return bf.check(tmp / "out", 26, now=lambda: T0)


def test_fresh_ok(tmp_path):
    real_backup(tmp_path, 3)
    ok, msg = run(tmp_path)
    assert ok and msg.startswith("OK")


def test_27h_old_alerts(tmp_path):
    real_backup(tmp_path, 27)
    ok, msg = run(tmp_path)
    assert not ok and "27.0 h old" in msg


def test_none_alerts(tmp_path):
    assert run(tmp_path)[0] is False
    (tmp_path / "out").mkdir()
    ok, msg = run(tmp_path)
    assert not ok and "no Velaris backup" in msg


@pytest.mark.parametrize("damage", ["truncate", "no_sidecar", "bad_sidecar", "no_manifest"])
def test_partial_or_corrupt_alerts(tmp_path, damage):
    a = real_backup(tmp_path, 1)
    side = Path(str(a) + ".sha256")
    if damage == "truncate":
        a.write_bytes(a.read_bytes()[:40])
    elif damage == "no_sidecar":
        side.unlink()
    elif damage == "bad_sidecar":
        side.write_text("0" * 64 + f"  {a.name}\n")
    else:  # valid tar.gz, matching checksum, but not a Velaris archive
        import hashlib
        import tarfile
        a.unlink()
        with tarfile.open(a, "w:gz") as t:
            t.add(side, arcname="other")
        side.write_text(hashlib.sha256(a.read_bytes()).hexdigest() + f"  {a.name}\n")
    ok, msg = run(tmp_path)
    assert not ok and "not good" in msg


def test_bad_newest_alerts_even_if_older_is_good(tmp_path):
    real_backup(tmp_path, 30)
    bad = tmp_path / "out" / f"velaris-data-{stamp(2)}.tar.gz"
    bad.write_bytes(b"junk")
    assert run(tmp_path)[0] is False


def test_cli_exit_codes(tmp_path, capsys):
    assert bf.main(["--dir", str(tmp_path / "nope")]) == 2
    assert "ALERT" in capsys.readouterr().err
