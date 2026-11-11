"""Model council: several models answer, judge each other blind, and one writes the final answer.

  1. answer     every member answers the question independently, in parallel.
                A member that fails is dropped; the council goes on with the rest.
  2. review     every member that answered ranks ALL the answers without knowing
                who wrote which. Labels (A, B, C...) are reshuffled for each
                reviewer so no answer benefits from always being listed first.
                The reply must be JSON; one retry, then that reviewer is dropped.
  3. score      code, not a model, works out the result: mean rank per answer
                (a member's vote for its own answer is not counted) and
                Kendall's W, a 0..1 measure of how much the reviewers agree.
  4. synthesise a chairman model writes one answer from the ranked answers and
                critiques. If the chairman fails, the top-ranked answer is returned.

`contested` is True when the reviewers disagree (W below CONTESTED_BELOW). The
council never acts on its own answer: the caller reads `contested` and decides
whether a person must look. Answers are model output, so they are fenced by
guard.wrap before another model reads them (an answer cannot instruct a reviewer).
"""
from __future__ import annotations

import hashlib
import random
import string
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from velaris.intel import guard, trace
from velaris.intel.llm import LLM, LLMError, extract_json

MAX_MEMBERS = 8          # cost ceiling: a council makes about 2n+1 model calls
CONTESTED_BELOW = 0.5    # Kendall's W under this: the reviewers do not agree


@dataclass
class CouncilResult:
    question: str
    answer: str
    chosen_by: str                                   # chairman | top_ranked | only_answer | none
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


def _parallel(members: Sequence[str], fn: Callable[[str], Any], stage: str,
              failed: Dict[str, str]) -> Dict[str, Any]:
    """Run fn(member) for every member at once; a failure is recorded, never raised."""
    def safe(member: str) -> Tuple[str, Any, str]:
        try:
            return member, fn(member), ""
        except LLMError as e:
            return member, None, str(e)[:200]

    out: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=len(members)) as pool:
        for member, value, error in pool.map(safe, members):
            if error or not value:
                failed[f"{stage}:{member}"] = error or "empty reply"
            else:
                out[member] = value
    return out


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
        text = llm.complete(prompt if attempt == 0 else prompt + "\n\nYour last reply was not valid. JSON only.",
                            model=reviewer, max_tokens=600, temperature=0.0, purpose="council.review").text
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


def council(question: str, *, models: Sequence[str], llm: Optional[LLM] = None,
            chairman: Optional[str] = None, context: str = "",
            seed: Optional[int] = None) -> CouncilResult:
    """Ask `models` (each "provider:name"), have them review each other blind, return one answer.

    `context` is extra material for the members; it is treated as untrusted data.
    `chairman` defaults to the first model. `seed` fixes the label shuffles (tests).
    """
    members = list(dict.fromkeys(models))[:MAX_MEMBERS]
    if not members:
        raise ValueError("a council needs at least one model")
    llm, rng = llm or LLM(), random.Random(seed)
    res = CouncilResult(question=question, answer="", chosen_by="none")

    ask = f"Question:\n{question}"
    if context:
        preamble, block = guard.wrap(context, label="background material")
        ask += f"\n\n{preamble}\n\n{block}"
    ask += "\n\nAnswer accurately and concisely. Say so plainly if you are not sure."
    res.answers = _parallel(members, lambda m: llm.complete(
        ask, model=m, max_tokens=900, purpose="council.answer").text, "answer", res.failed)
    answered = list(res.answers)

    if len(answered) >= 2:
        # shuffles are drawn here, in order, so a seed gives the same labels on every run
        rngs = {m: random.Random(rng.random()) for m in answered}
        reviews = _parallel(answered, lambda m: _review(llm, m, question, res.answers, rngs[m]),
                            "review", res.failed)
        res.rankings = {m: r[0] for m, r in reviews.items()}
        for _, notes in reviews.values():
            for member, note in notes.items():
                res.critiques.setdefault(member, []).append(note)
        res.mean_rank = _score(res.rankings, answered)
        res.agreement = kendall_w(list(res.rankings.values()))
        res.contested = res.agreement is not None and res.agreement < CONTESTED_BELOW

    if len(answered) == 1:
        res.answer, res.chosen_by = res.answers[answered[0]], "only_answer"
    elif answered:
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
        try:
            text = llm.complete(prompt, model=chairman or members[0], max_tokens=1200,
                                purpose="council.chairman").text
            if text:
                res.answer, res.chosen_by = text, "chairman"
        except LLMError as e:
            res.failed[f"chairman:{chairman or members[0]}"] = str(e)[:200]

    res.trace_hash = trace.append("council", "result", {
        "question_sha256": hashlib.sha256(question.encode()).hexdigest(), "members": members,
        "answered": answered, "rankings": res.rankings, "mean_rank": res.mean_rank,
        "agreement": res.agreement, "contested": res.contested, "chosen_by": res.chosen_by,
        "failed": res.failed, "answer_sha256": hashlib.sha256(res.answer.encode()).hexdigest(),
    })["hash"]
    return res
