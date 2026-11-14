"""KAN-108: domain verification has a real resolver, the outbox and retention run on their own, crashed sends are retried."""
import asyncio

import pytest

from velaris.api import background
from velaris.core.filelock import FileLock
from velaris.intel.paths import data_dir
from velaris.mail import api as mail_api
from velaris.mail.dnsauth import UnavailableResolver
from velaris.tests.mail_helpers import make_world


def test_default_mail_deps_use_a_real_resolver_when_dnspython_is_installed():
    pytest.importorskip("dns.resolver")
    class S: gate = None; llm = None                      # noqa: E702
    assert not isinstance(mail_api.default_deps(S()).inbound.resolver, UnavailableResolver)


def test_a_submission_stuck_in_sending_after_a_crash_is_requeued_then_given_up():
    store, ob, _ib, clock, relay, boxes = make_world()
    cols = [r[1] for r in store.q("PRAGMA table_info(submission)")]
    row = {c: "" for c in cols}
    row.update(id="s1", org="acme", state="sending", send_at=clock() - 2000, attempts=1, created=clock() - 3000, payload_hash="h")
    store.run(f"INSERT INTO submission({','.join(row)}) VALUES ({','.join('?' * len(row))})", tuple(row.values()))
    assert ob.recover_stuck(clock()) == 1
    assert store.one("SELECT state FROM submission WHERE id='s1'")["state"] == "approved"
    store.run("UPDATE submission SET state='sending', send_at=?, attempts=4 WHERE id='s1'", (clock() - 2000,))
    ob.recover_stuck(clock())
    assert store.one("SELECT state FROM submission WHERE id='s1'")["state"] == "failed"


def test_a_job_runs_unless_another_process_holds_its_lock_and_failures_do_not_escape():
    ran = []
    assert background.run_once("t", lambda: ran.append(1)) and ran == [1]
    with FileLock(data_dir() / "shared" / "job-t.lock", timeout=0):
        import multiprocessing as mp
        # same-process re-entry would succeed; a second PROCESS must be refused
        q = mp.get_context("fork").Queue()
        p = mp.get_context("fork").Process(target=lambda: q.put(background.run_once("t", lambda: None)))
        p.start(); p.join()                                # noqa: E702
        assert q.get() is False
    assert background.run_once("boom", lambda: 1 / 0) is True


def test_lifespan_runs_jobs_and_stops_them():
    hits = []

    async def go():
        async with background.lifespan([("tick", 0.01, lambda: hits.append(1)), ("off", 0, lambda: hits.append("never"))])(None):
            await asyncio.sleep(0.15)
    asyncio.run(go())
    assert hits and "never" not in hits
