"""Model council: several models answer, judge each other blind, and one writes the final answer.

  1. answer     every member answers the question independently. Hosted models run
                in parallel; models on the local Ollama server run one after another,
                because that server works through one request at a time and a model
                waiting in its queue would otherwise use up its time limit doing nothing.
                A member that fails or exceeds the per-model time limit is recorded in
                `failed` and left out; the council goes on with the rest.
     quorum     fewer answers than `min_quorum` (default 2, or 1 for a one-model
                council) is not a council: the result has status "insufficient" and
                no answer. The answers that did arrive stay in `answers` for a person.
  2. review     every member that answered ranks ALL the answers without knowing
                who wrote which. Labels (A, B, C...) are reshuffled for each
                reviewer so no answer benefits from always being listed first.
                The reply must be JSON; one retry, then that reviewer is dropped.
  3. score      code, not a model, works out the result: mean rank per answer
                (a member's vote for its own answer is not counted) and
                Kendall's W, a 0..1 measure of how much the reviewers agree.
  4. synthesise a chairman model writes one answer from the ranked answers and
                critiques. If the chairman fails, the top-ranked answer is returned.

`contested` is True when the reviewers disagree (W below CONTESTED_BELOW) or when
too few reviews came back to measure agreement at all. `summary` says in one line
who answered, who reviewed and who dropped out and why. The
council never acts on its own answer: the caller reads `contested` and decides
whether a person must look. Answers are model output, so they are fenced by
guard.wrap before another model reads them (an answer cannot instruct a reviewer).
"""
from __future__ import annotations

import hashlib
import os
import random
import string
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as CallTimeout
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from velaris.intel import router
from velaris.intel import guard, trace
from velaris.intel.llm import LLM, TIMEOUT_S, LLMError, call_timeout, extract_json

MAX_MEMBERS = 8          # cost ceiling: a council makes about 2n+1 model calls
CONTESTED_BELOW = 0.5    # Kendall's W under this: the reviewers do not agree
LOCAL_PROVIDERS = ("ollama",)      # served by one local process: called one at a time


def default_timeout() -> float:
    """Seconds one member may take for one call: VELARIS_COUNCIL_TIMEOUT, else the gateway's limit."""
    return float(os.environ.get("VELARIS_COUNCIL_TIMEOUT") or TIMEOUT_S)


@dataclass
class CouncilResult:
    question: str
    answer: str
    chosen_by: str                                   # chairman | top_ranked | only_answer | none
    status: str = "ok"                               # ok | insufficient (too few members answered: no answer)
    members: List[str] = field(default_factory=list)               # everyone who was asked
    answered: List[str] = field(default_factory=list)              # those whose answer arrived in time
    quorum: int = 1                                  # answers needed for a result
    timeout_s: float = 0.0                           # per member, per call
    summary: str = ""                                # who answered, who reviewed, who dropped out and why
    answers: Dict[str, str] = field(default_factory=dict)          # member -> its answer
    rankings: Dict[str, List[str]] = field(default_factory=dict)   # reviewer -> members, best first
    critiques: Dict[str, List[str]] = field(default_factory=dict)  # member -> what reviewers said of it
    mean_rank: Dict[str, float] = field(default_factory=dict)      # member -> 1.0 is best
    agreement: Optional[float] = None                # Kendall's W; None with fewer than 2 reviewers
    contested: bool = False
    failed: Dict[str, str] = field(default_factory=dict)           # "stage:member" -> reason
    trace_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def kendall_w(rankings: Sequence[Sequence[str]]) -> Optional[float]:
    """Agreement between complete rankings of the same items: 1 = identical, 0 = none."""
    m = len(rankings)
    n = len(rankings[0]) if rankings else 0
    if m < 2 or n < 2:
        return None
    sums = {item: 0 for item in rankings[0]}
    for r in rankings:
        for pos, item in enumerate(r, start=1):
            sums[item] += pos
    mean = m * (n + 1) / 2
    s = sum((v - mean) ** 2 for v in sums.values())
    return round(12 * s / (m * m * (n ** 3 - n)), 4)


def _bounded(pool: ThreadPoolExecutor, fn: Callable[[str], Any], member: str,
             timeout_s: float) -> Tuple[Any, str]:
    """(fn(member), "") or (None, why not). Never raises for a model failure and never waits
    longer than timeout_s: a call that overruns is abandoned and reported as a timeout."""
    def call() -> Any:
        with call_timeout(timeout_s):       # also ends the HTTP request itself at the limit
            return fn(member)

    future = pool.submit(call)
    try:
        return future.result(timeout=timeout_s), ""
    except CallTimeout:
        future.cancel()
        return None, f"timeout after {timeout_s:g}s"
    except LLMError as e:
        return None, str(e)[:200]


def _parallel(members: Sequence[str], fn: Callable[[str], Any], stage: str,
              failed: Dict[str, str], timeout_s: float) -> Dict[str, Any]:
    """Run fn(member) for every member; a failure or timeout is recorded, never raised.

    Each hosted model is its own lane; local models share one lane and run in turn, so
    each gets the whole time limit. An abandoned call keeps its thread until the HTTP
    request ends (at the same limit); nothing waits for it.
    """
    lanes: Dict[str, List[str]] = {}
    for m in members:
        lanes.setdefault("local" if m.split(":")[0] in LOCAL_PROVIDERS else m, []).append(m)
    calls = ThreadPoolExecutor(max_workers=len(members))
    out: Dict[str, Any] = {}
    try:
        with ThreadPoolExecutor(max_workers=len(lanes)) as heads:
            for lane in heads.map(lambda ms: [(m, *_bounded(calls, fn, m, timeout_s)) for m in ms],
                                  lanes.values()):
                for member, value, error in lane:
                    if error or not value:
                        failed[f"{stage}:{member}"] = error or "empty reply"
                    else:
                        out[member] = value
    finally:
        calls.shutdown(wait=False, cancel_futures=True)
    return {m: out[m] for m in members if m in out}      # the order the members were given in


def _review(llm: LLM, reviewer: str, question: str, answers: Dict[str, str],
            rng: random.Random) -> Tuple[List[str], Dict[str, str]]:
    """One blind review. Returns (members best first, critique per member)."""
    order = list(answers)
    rng.shuffle(order)
    by_label = dict(zip(string.ascii_uppercase, order))
    listing = "\n\n".join(f"Answer {label}:\n{answers[m]}" for label, m in by_label.items())
    preamble, block = guard.wrap(listing, label="a set of candidate answers written by other models")
    prompt = (f"Question:\n{question}\n\n{preamble}\n\n{block}\n\n"
              "Judge each candidate answer for correctness, completeness and soundness of reasoning. "
              "Give one sentence of critique per answer, then rank them. "
              'Reply with JSON only: {"critiques": {"A": "..."}, "ranking": ["<best label>", "...", "<worst label>"]} '
              f"using each of these labels exactly once: {', '.join(by_label)}.")
    last = "no reply"
    for attempt in range(2):
        text = router.complete("worker", prompt if attempt == 0 else prompt + "\n\nYour last reply was not valid. JSON only.",
                            llm=llm, model=reviewer, sensitivity="restricted", max_tokens=600, temperature=0.0, purpose="council.review").text
        try:
            data = extract_json(text)
            ranking = [str(x).strip().upper()[-1:] for x in data["ranking"]]
            if sorted(ranking) != sorted(by_label):
                raise LLMError("ranking does not use each label exactly once")
        except (LLMError, KeyError, TypeError) as e:
            last = str(e)[:120]
            continue
        notes = data.get("critiques") if isinstance(data.get("critiques"), dict) else {}
        return ([by_label[x] for x in ranking],
                {by_label[k]: str(v)[:400] for k, v in notes.items() if k in by_label})
    raise LLMError(f"invalid review: {last}")


def _score(rankings: Dict[str, List[str]], members: Sequence[str]) -> Dict[str, float]:
    """Mean position of each member's answer, ignoring the vote each member cast for itself."""
    positions: Dict[str, List[int]] = {m: [] for m in members}
    for reviewer, ranking in rankings.items():
        for pos, member in enumerate([m for m in ranking if m != reviewer], start=1):
            positions[member].append(pos)
    return {m: round(sum(p) / len(p), 3) for m, p in positions.items() if p}


def _summary(res: CouncilResult) -> str:
    out = [f"{len(res.answered)} of {len(res.members)} members answered"
           + (f" ({', '.join(res.answered)})" if res.answered else "")]
    if res.rankings:
        out.append(f"{len(res.rankings)} reviewed ({', '.join(res.rankings)})")
    out += [f"{who} failed: {why}" for who, why in res.failed.items()]
    if res.status == "insufficient":
        out.append(f"no answer given: {res.quorum} answers were needed")
    return "; ".join(out)


def council(question: str, *, models: Sequence[str], llm: Optional[LLM] = None,
            chairman: Optional[str] = None, context: str = "", seed: Optional[int] = None,
            timeout_s: Optional[float] = None, min_quorum: Optional[int] = None) -> CouncilResult:
    """Ask `models` (each "provider:name"), have them review each other blind, return one answer.

    `context` is extra material for the members; it is treated as untrusted data.
    `chairman` defaults to the first model that answered. `seed` fixes the label shuffles (tests).
    `timeout_s` is the time one member gets for one call (default: default_timeout()).
    `min_quorum` is how many members must answer for there to be a result (default 2, or 1
    when only one model was given). Below it: status "insufficient", empty answer.
    """
    members = list(dict.fromkeys(models))[:MAX_MEMBERS]
    if not members:
        raise ValueError("a council needs at least one model")
    timeout_s = default_timeout() if timeout_s is None else float(timeout_s)
    quorum = min(2, len(members)) if min_quorum is None else int(min_quorum)
    if timeout_s <= 0 or not 1 <= quorum <= len(members):
        raise ValueError("timeout_s must be positive and min_quorum between 1 and the number of models")
    llm, rng = llm or LLM(), random.Random(seed)
    res = CouncilResult(question=question, answer="", chosen_by="none", members=members,
                        quorum=quorum, timeout_s=timeout_s)

    ask = f"Question:\n{question}"
    if context:
        preamble, block = guard.wrap(context, label="background material")
        ask += f"\n\n{preamble}\n\n{block}"
    ask += "\n\nAnswer accurately and concisely. Say so plainly if you are not sure."
    res.answers = _parallel(members, lambda m: router.complete(
        "worker", ask, llm=llm, model=m, sensitivity="restricted", max_tokens=900, purpose="council.answer").text, "answer", res.failed, timeout_s)
    answered = res.answered = list(res.answers)
    enough = len(answered) >= quorum
    if not enough:
        res.status = "insufficient"

    if enough and len(answered) >= 2:
        # shuffles are drawn here, in order, so a seed gives the same labels on every run
        rngs = {m: random.Random(rng.random()) for m in answered}
        reviews = _parallel(answered, lambda m: _review(llm, m, question, res.answers, rngs[m]),
                            "review", res.failed, timeout_s * 2)      # a review may take one retry
        res.rankings = {m: r[0] for m, r in reviews.items()}
        for _, notes in reviews.values():
            for member, note in notes.items():
                res.critiques.setdefault(member, []).append(note)
        res.mean_rank = _score(res.rankings, answered)
        res.agreement = kendall_w(list(res.rankings.values()))
        # Several answers and no measurable agreement about them is as unsettled as disagreement.
        res.contested = res.agreement is None or res.agreement < CONTESTED_BELOW

    if not enough:
        pass                     # too few voices: no answer is better than a thin one
    elif len(answered) == 1:
        res.answer, res.chosen_by = res.answers[answered[0]], "only_answer"
    else:
        ranked = sorted(answered, key=lambda m: res.mean_rank.get(m, float("inf")))
        res.answer, res.chosen_by = res.answers[ranked[0]], "top_ranked"
        listing = "\n\n".join(
            f"Answer {i} (mean rank from peers: {res.mean_rank.get(m, 'not ranked')}; 1 is best):\n{res.answers[m]}"
            + "".join(f"\n- reviewer note: {c}" for c in res.critiques.get(m, []))
            for i, m in enumerate(ranked, start=1))
        preamble, block = guard.wrap(listing, label="candidate answers with peer rankings and notes")
        prompt = (f"Question:\n{question}\n\n{preamble}\n\n{block}\n\n"
                  "Write the single best answer to the question. Rely most on the better-ranked answers and on "
                  "points several answers share. Where the answers conflict on something that matters, say that "
                  "it is disputed instead of silently picking a side. Do not mention the candidates or the ranking.")
        chair = chairman or answered[0]       # a member that just failed would only fail again
        text = _parallel([chair], lambda m: router.complete(
            "worker", prompt, llm=llm, model=m, sensitivity="restricted", max_tokens=1200, purpose="council.chairman").text,
            "chairman", res.failed, timeout_s).get(chair)
        if text:
            res.answer, res.chosen_by = text, "chairman"

    res.summary = _summary(res)
    res.trace_hash = trace.append("council", "result", {
        "question_sha256": hashlib.sha256(question.encode()).hexdigest(), "members": members,
        "answered": answered, "rankings": res.rankings, "mean_rank": res.mean_rank,
        "agreement": res.agreement, "contested": res.contested, "chosen_by": res.chosen_by,
        "status": res.status, "quorum": quorum, "timeout_s": timeout_s,
        "failed": res.failed, "answer_sha256": hashlib.sha256(res.answer.encode()).hexdigest(),
    })["hash"]
    return res
