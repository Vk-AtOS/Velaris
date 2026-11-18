"""KAN-136: the replay cache and rate counters are shared by every worker process."""
import multiprocessing as mp
import os

import pytest

from velaris.core.shared import NonceStore, RateStore, StoreFull


def _claim(data, nonce, q):
    os.environ["VELARIS_DATA"] = data
    q.put(NonceStore().seen_before(nonce, 120))


def test_a_nonce_replayed_against_another_process_is_refused(tmp_path):
    ctx, q = mp.get_context("fork"), mp.get_context("fork").Queue()
    ps = [ctx.Process(target=_claim, args=(str(tmp_path), "n" * 24, q)) for _ in range(2)]
    for p in ps:
        p.start()
        p.join()                                              # one after the other: two workers, one nonce
    assert sorted([q.get(), q.get()]) == [False, True]


def test_nonce_expires_and_a_full_store_refuses():
    s = NonceStore(max_live=3)
    assert s.seen_before("a", 10, now=100) is False and s.seen_before("a", 10, now=105) is True
    assert s.seen_before("a", 10, now=111) is False           # expired: usable again
    s._last_sweep = 0
    s.seen_before("b", 10, now=200)
    s.seen_before("c", 10, now=200)
    s.seen_before("d", 10, now=200)
    s._last_sweep = 0
    with pytest.raises(StoreFull):
        s.seen_before("e", 10, now=201)


def _hit(data, q):
    os.environ["VELARIS_DATA"] = data
    r = RateStore()
    q.put(sum(r.allow("k", 5, 60, now=1000) for _ in range(5)))


def test_rate_limit_counts_across_processes(tmp_path):
    ctx, q = mp.get_context("fork"), mp.get_context("fork").Queue()
    for _ in range(2):
        p = ctx.Process(target=_hit, args=(str(tmp_path), q))
        p.start()
        p.join()
    assert q.get() + q.get() == 5                             # 10 attempts across two workers, limit 5 in total
    assert RateStore().allow("k", 5, 60, now=1061) is True    # window slid


def test_streamed_readers_match_read_lines_and_keep_memory_flat(tmp_path):
    """KAN-136: iter_lines / read_tail give what read_lines gives without holding the file; a torn line is skipped."""
    from velaris.agentkit.state import append_line, iter_lines, read_lines, read_tail
    p = tmp_path / "s.jsonl"
    for i in range(50):
        append_line(p, {"i": i})
    with open(p, "a") as f:
        f.write('{"i": 5')                               # torn last line
    assert list(iter_lines(p)) == read_lines(p)
    assert read_tail(p, 3) == [{"i": 48}, {"i": 49}]     # the torn line takes one of the three slots and is skipped
    assert read_tail(tmp_path / "none", 3) == [] and list(iter_lines(tmp_path / "none")) == []
