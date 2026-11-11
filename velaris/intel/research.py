"""Deep research: a question in, a cited report out, with every claim checked in code.

  1. plan      one model call splits the question into a few sub-questions.
               A failed or unreadable plan falls back to the question itself.
  2. gather    per sub-question: search, skip URLs already visited, scrape.
               Pages that fail or that the guard blocks are skipped. Total
               pages are capped, and so are pages per site.
  3. filter    each page is chunked and embedded; only the chunks closest to
               the sub-question go to a model. This is the main cost control.
  4. learn     one model call per page returns {claim, quote} pairs. Code then
               looks for each quote in the page text. No quote, no learning:
               the pair is dropped and counted as rejected.
  5. reflect   one model call says "enough" or names up to two gaps, which
               become the next round's sub-questions. Rounds are capped, and a
               round that adds nothing ends the loop.
  6. report    one model call writes the answer from the numbered learnings
               only. Code (research_report) removes every sentence without a
               valid citation and appends the source list itself.

Source numbers come from a registry (first source with a verified learning is
1) and never change between rounds. Any model or web failure ends in a partial
result whose `stopped_because` says what happened; with no learnings the report
says so and no model is asked to answer from memory.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urlsplit

from velaris.intel import guard, trace, web
from velaris.intel.llm import LLM, LLMError, cosine, extract_json
from velaris.intel.research_report import findings_body, sources_section, verify_report
from velaris.intel.web_fetch import Fetcher, FetchError
from velaris.intel.web_markdown import chunk

# ponytail: one fixed threshold for every embedding model. Tuned for the offline
# hashed embedding and nomic-embed-text; re-tune if the embedding model changes.
MIN_SIMILARITY = 0.2
CHUNKS_PER_PAGE = 4
CHUNK_CHARS = 1500
MAX_PAGE_CHARS = 60000       # only the start of a very long page is embedded
PAGES_PER_DOMAIN = 2
SEARCH_LIMIT = 6
MIN_QUOTE_CHARS = 15         # shorter "quotes" occur in any page and prove nothing
LEARNINGS_PER_PAGE = 5
FOLLOW_UPS = 2

SearchFn = Callable[..., List[Dict[str, str]]]


@dataclass
class Learning:
    n: int                   # source number in the registry; cited as [n]
    claim: str
    quote: str
    url: str
    title: str
    page_sha256: str
    trace_hash: str


@dataclass
class ResearchResult:
    question: str
    report: str = ""
    learnings: List[Learning] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)
    rejected_learnings: int = 0
    rounds: int = 0
    stopped_because: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class _Run:
    """Working state of one research() call."""
    question: str
    llm: LLM
    model: Optional[str]
    fetcher: Optional[Fetcher]
    search_fn: SearchFn
    max_sources: int
    result: ResearchResult
    visited: Set[str] = field(default_factory=set)
    per_domain: Dict[str, int] = field(default_factory=dict)
    registry: Dict[str, int] = field(default_factory=dict)      # url -> source number
    seen_quotes: Set[tuple] = field(default_factory=set)
    pages_read: int = 0
    errors: List[str] = field(default_factory=list)


def _plain(text: str) -> str:
    """Text as compared for quote checking: no markdown marks, single spaces, lower case."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", guard.normalise(text))     # links keep their label
    return " ".join(re.sub(r"[*_`]", "", text).split()).lower()


def _questions(raw: Any, limit: int) -> List[str]:
    """Up to `limit` distinct, non-empty question strings from a model's JSON."""
    out: List[str] = []
    for q in raw if isinstance(raw, list) else []:
        q = " ".join(q.split())[:300] if isinstance(q, str) else ""
        if q and q.lower() not in {x.lower() for x in out}:
            out.append(q)
    return out[:limit]


def _plan(run: _Run, max_subquestions: int, scope_note: str) -> List[str]:
    prompt = (f"Research question: {run.question}\n"
              + (f"Scope: {scope_note}\n" if scope_note else "")
              + f"\nBreak this into at most {max_subquestions} focused sub-questions that can each be "
              "answered by a web search and that together answer the question. "
              'Reply with JSON only: {"sub_questions": ["...", "..."]}')
    error = ""
    subs: List[str] = []
    try:
        raw = extract_json(run.llm.complete(prompt, model=run.model, max_tokens=400, temperature=0.2,
                                            purpose="research.plan").text)
        subs = _questions(raw.get("sub_questions") if isinstance(raw, dict) else raw, max_subquestions)
    except LLMError as e:
        error = str(e)[:120]
    fallback = not subs
    trace.append("research", "research.plan", {"question": run.question[:300], "fallback": fallback,
                                               "sub_questions": subs or [run.question], "error": error})
    return subs or [run.question]


def _relevant_text(run: _Run, page: web.Page, subq: str) -> str:
    """The chunks of the page closest to the sub-question, or "" if none is close enough."""
    chunks = chunk(page.markdown[:MAX_PAGE_CHARS], CHUNK_CHARS)
    if not chunks:
        return ""
    texts = [f"{c['heading']}\n{c['text']}".strip() for c in chunks]
    vectors = run.llm.embed([subq] + texts)
    scored = sorted(((cosine(vectors[0], v), t) for v, t in zip(vectors[1:], texts)), reverse=True)
    return "\n\n".join(t for score, t in scored[:CHUNKS_PER_PAGE] if score >= MIN_SIMILARITY)


def _learn(run: _Run, page: web.Page, subq: str, text: str) -> None:
    """Extract {claim, quote} pairs from one page and keep those whose quote is really there."""
    url = page.final_url or page.url
    preamble, block = guard.wrap(text, label=f"text from the web page {url}")
    prompt = (f"{preamble}\n\n{block}\n\nQuestion: {subq}\n\n"
              f"List at most {LEARNINGS_PER_PAGE} facts from that text that help answer the question. "
              "For each give a one-sentence claim and a quote: one sentence or phrase copied from the text "
              "character for character, which supports the claim. Use nothing you know from elsewhere. "
              'Reply with JSON only: {"learnings": [{"claim": "...", "quote": "..."}]}. '
              'If the text does not help, reply {"learnings": []}.')
    try:
        raw = extract_json(run.llm.complete(prompt, model=run.model, max_tokens=900, temperature=0.0,
                                            purpose="research.learnings").text)
    except LLMError as e:
        run.errors.append(f"learnings: {str(e)[:120]}")
        return
    items = raw.get("learnings") if isinstance(raw, dict) else raw
    haystack = _plain(page.markdown)
    page_sha = hashlib.sha256(page.markdown.encode()).hexdigest()
    title = " ".join(page.title.split()) or url
    for item in (items if isinstance(items, list) else [])[:LEARNINGS_PER_PAGE * 2]:
        claim, quote = (str(item.get(k) or "").strip() for k in ("claim", "quote")) \
            if isinstance(item, dict) else ("", "")
        needle = _plain(quote)
        if not claim or len(needle) < MIN_QUOTE_CHARS or needle not in haystack:
            run.result.rejected_learnings += 1      # the core guarantee: no learning without a real quote
            continue
        if (url, needle) in run.seen_quotes:
            continue
        run.seen_quotes.add((url, needle))
        if url not in run.registry:
            run.registry[url] = len(run.registry) + 1
            run.result.sources.append({"n": run.registry[url], "title": title, "url": url, "sha256": page_sha})
        n = run.registry[url]
        entry = trace.append("research", "research.learning", {
            "n": n, "url": url, "page_sha256": page_sha, "claim": claim[:300],
            "quote_sha256": hashlib.sha256(quote.encode()).hexdigest()})
        run.result.learnings.append(Learning(n=n, claim=claim, quote=quote, url=url, title=title,
                                             page_sha256=page_sha, trace_hash=entry["hash"]))


def _gather(run: _Run, subq: str, budget: int) -> None:
    """Search one sub-question and read up to `budget` new pages."""
    try:
        hits = run.search_fn(subq, limit=SEARCH_LIMIT, f=run.fetcher)
    except (FetchError, LLMError, ValueError, KeyError, OSError) as e:
        run.errors.append(f"search: {type(e).__name__}: {str(e)[:100]}")
        return
    for hit in hits:
        if budget <= 0 or run.pages_read >= run.max_sources:
            return
        url = str(hit.get("url") or "")
        domain = (urlsplit(url).hostname or "").lower().removeprefix("www.")
        if not url or url in run.visited or run.per_domain.get(domain, 0) >= PAGES_PER_DOMAIN:
            continue
        run.visited.add(url)
        page = web.scrape(url, f=run.fetcher)
        if not page.ok or page.risk == "block" or not page.markdown.strip():
            continue
        if page.final_url != url:
            if page.final_url in run.visited:      # a redirect to a page already read
                continue
            run.visited.add(page.final_url)
        run.per_domain[domain] = run.per_domain.get(domain, 0) + 1
        run.pages_read += 1
        budget -= 1
        text = _relevant_text(run, page, subq)
        if text:
            _learn(run, page, subq, text)


def _numbered(learnings: List[Learning], with_quotes: bool) -> str:
    return "\n".join(f"[{x.n}] {x.claim}" + (f' (source text: "{x.quote}")' if with_quotes else "")
                     for x in learnings)


def _reflect(run: _Run) -> List[str]:
    """Follow-up sub-questions for the gaps, or [] when the learnings are enough. Raises LLMError."""
    preamble, block = guard.wrap(_numbered(run.result.learnings, False), label="findings taken from web pages")
    prompt = (f"{preamble}\n\n{block}\n\nResearch question: {run.question}\n\n"
              "Do those findings answer the research question? If they do, reply "
              '{"enough": true, "follow_ups": []}. If something important is missing, reply '
              f'{{"enough": false, "follow_ups": ["..."]}} with at most {FOLLOW_UPS} new search questions '
              "for the gaps. Reply with JSON only.")
    raw = extract_json(run.llm.complete(prompt, model=run.model, max_tokens=300, temperature=0.2,
                                        purpose="research.reflect").text)
    if not isinstance(raw, dict):
        raise LLMError("reflection reply was not a JSON object")
    if raw.get("enough") is True:
        return []
    return _questions(raw.get("follow_ups"), FOLLOW_UPS)


def _write_report(run: _Run, scope_note: str) -> None:
    """Fill result.report and result.unsupported. With no learnings, no model is asked anything."""
    res = run.result
    title = f"# {run.question}\n\n"
    if not res.learnings:
        res.report = (title + "No verifiable information was found for this question, so no answer is given. "
                      f"Pages read: {run.pages_read}. Reason research stopped: {res.stopped_because}.")
        trace.append("research", "research.report", {"learnings": 0, "sources": 0, "model_written": False,
                                                     "stopped_because": res.stopped_because})
        return
    preamble, block = guard.wrap(_numbered(res.learnings, True), label="numbered findings taken from web pages")
    prompt = (f"{preamble}\n\n{block}\n\nResearch question: {run.question}\n"
              + (f"Scope: {scope_note}\n" if scope_note else "")
              + "\nWrite a short markdown answer to the research question using ONLY those findings. "
              "End every sentence and every bullet with the number of the finding it rests on, like [1] "
              "or [1][2]. Leave out anything the findings do not support, and add no knowledge of your own. "
              "Use '#' headings for structure, no tables, and no list of sources.")
    body, model_written = "", True
    try:
        draft = run.llm.complete(prompt, model=run.model, max_tokens=1200, temperature=0.2,
                                 purpose="research.report").text
        body, res.unsupported = verify_report(draft, set(run.registry.values()))
    except LLMError as e:
        res.stopped_because = f"error:report: {str(e)[:120]}"
    if not body:      # no draft, or nothing in it survived checking: list the verified findings instead
        model_written = False
        body = ("The model's draft could not be used, so the verified findings are listed as they were "
                "extracted.\n\n" + findings_body(res.learnings))
    res.report = title + body + "\n\n" + sources_section(res.sources)
    trace.append("research", "research.report", {
        "learnings": len(res.learnings), "sources": len(res.sources), "unsupported": len(res.unsupported),
        "model_written": model_written, "stopped_because": res.stopped_because,
        "report_sha256": hashlib.sha256(res.report.encode()).hexdigest()})


def research(question: str, *, llm: Optional[LLM] = None, model: Optional[str] = None,
             fetcher: Optional[Fetcher] = None, max_subquestions: int = 4, max_sources: int = 8,
             max_rounds: int = 2, scope_note: str = "", search_fn: SearchFn = web.search) -> ResearchResult:
    """Research a question on the web and return a report in which every sentence is cited.

    Never raises for a model or web failure: the result is partial and
    `stopped_because` says why. `search_fn` has the signature of web.search.
    """
    res = ResearchResult(question=question)
    run = _Run(question=question, llm=llm or LLM(), model=model, fetcher=fetcher, search_fn=search_fn,
               max_sources=max_sources, result=res)
    queue = _plan(run, max_subquestions, scope_note)
    res.stopped_because = "max_rounds"
    for rnd in range(1, max_rounds + 1):
        res.rounds = rnd
        before, errors_before = len(res.learnings), len(run.errors)
        for i, subq in enumerate(queue):
            _gather(run, subq, math.ceil((max_sources - run.pages_read) / (len(queue) - i)))
        added = len(res.learnings) - before
        trace.append("research", "research.round", {
            "round": rnd, "sub_questions": len(queue), "pages_read": run.pages_read, "new_learnings": added,
            "learnings": len(res.learnings), "rejected": res.rejected_learnings,
            "errors": run.errors[errors_before:]})
        if not run.pages_read:
            res.stopped_because = f"error:{run.errors[-1]}" if run.errors else "no_sources"
            break
        if not added:
            failed = run.errors[errors_before:]
            res.stopped_because = f"error:{failed[-1]}" if failed else "no_new_learnings"
            break
        if rnd == max_rounds:
            break
        try:
            queue = _reflect(run)
        except LLMError as e:
            res.stopped_because = f"error:reflect: {str(e)[:120]}"
            break
        if not queue:
            res.stopped_because = "enough"
            break
    _write_report(run, scope_note)
    return res
