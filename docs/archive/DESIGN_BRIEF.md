# Velaris design brief: how the reference open-source projects work

Snapshot date 2026-11-11. Stars/licence/last push from `gh api repos/OWNER/REPO`. Paths are relative to each repo's default branch unless noted.
Conventions: **[read]** = taken from source/docs read in this session; **[inferred]** = my reading between the lines, not verified in code; **[not read]** = metadata only, no source opened.
Licence rule: for COPYLEFT / NO-LICENCE / source-available rows, re-implement ideas only; never copy code or long prompt text.

---

## 1. Web search + crawl + scrape to LLM-ready markdown

| Repo | Stars | Licence (SPDX) | Copyleft? | Last push |
|---|---|---|---|---|
| firecrawl/firecrawl | 200.6k | AGPL-3.0 | **YES - ideas only** | 2026-11-11 |
| unclecode/crawl4ai | 87.2k | Apache-2.0 | no | 2026-11-10 |
| adbar/trafilatura | 7.1k | Apache-2.0 | no | 2026-11-10 |
| jina-ai/reader | 12.3k | Apache-2.0 | no | 2026-05-22 [not read] |
| mozilla/readability | 11.5k | Apache-2.0 | no | 2026-08-04 [not read] |

### How it works
1. **Engine waterfall (firecrawl)** [read `apps/api/src/scraper/scrapeURL/engines/index.ts`]. Every fetch engine declares a feature-support map (waitFor, actions, pdf, stealthProxy, ...) and an integer `quality`. Cache/index lookup has the highest quality (1000+, "always tried first"), then headless Chrome (50), a retry variant (45), playwright (20), TLS-fingerprint client (10), plain `fetch` (5); negative quality is reserved for speciality engines (PDF, stealth proxies). `buildFallbackList` filters engines by the features the request needs and sorts by quality.
2. **Staggered race, not strict sequence** [read `scrapeURL/index.ts` ~L905-990]. Start engine 1; if it has not finished within `engineMaxReasonableTime + WATERFALL_DELAY`, start engine 2 *without cancelling engine 1*, and `Promise.race` all in-flight engines. First acceptable result wins and aborts the rest.
3. **Success test per engine** [read `scrapeURL/index.ts` ~L745-830]. Convert the HTML to markdown with main-content-only on; if empty, retry with main-content off. Accept if markdown is non-empty OR the status code is not 2xx/304 (an error page is still a real answer). If status is 401/403/429 and proxy mode is auto, raise an "add feature: stealthProxy" error, which rebuilds the fallback list with the new requirement. Typed errors (AddFeature/RemoveFeature/SSL/DNS/UnsupportedFile) short-circuit; a generic engine error just moves to the next engine; exhausting the list raises NoEnginesLeft.
4. **Block detection (crawl4ai)** [read `crawl4ai/antibot_detector.py`]. Tiered regexes: tier 1 = structural markers unique to block pages (Akamai reference id, Cloudflare challenge form/script, PerimeterX app id, DataDome/Incapsula/Sucuri markers) fire on any page size; tier 2 = generic words, only on short pages or error status; tier 3 = structural-integrity checks for empty shells. Stated philosophy: false positives are cheap (fallback rescues them), false negatives are catastrophic.
5. **Boilerplate removal, selector list (firecrawl)** [read `scrapeURL/lib/removeUnwantedElements.ts`]. Always drop `script, style, noscript, meta, head`. With `onlyMainContent`, drop ~45 selectors: `header, footer, nav, aside`, class/id variants of header/footer/sidebar/modal/popup/ad/social/menu/breadcrumbs/share/widget/cookie, captcha iframes; a small force-include list (`#main`, ...) overrides. User `includeTags` builds a fresh root from matches; `excludeTags` supports `*regex*` matching against tag name and `attr="value"`.
6. **Boilerplate removal, scored pruning (crawl4ai)** [read `content_filter_strategy.py` `PruningContentFilter`]. Recursive top-down DOM walk. For each node compute: text_density = text_len/html_len (weight 0.4); 1 - link_density (0.2); tag weight (0.2; article 1.5, h1 1.2, p 1.0, div 0.5, span 0.3); class/id negative-pattern penalty (0.1); log(text_len+1) (0.1); weighted mean. Remove the subtree if score < 0.48 (fixed) or a dynamic threshold (x0.8 for important tags, x0.9 if text ratio > 0.4, x1.2 if link ratio > 0.6); otherwise recurse into children. Optional min-word count forces removal. Preserve-lists bypass scoring.
7. **Boilerplate removal, extractor ensemble (trafilatura)** [read `core.py`, `external.py`]. Run own XPath/rule extractor; run a readability-style extractor on a copy; pick by heuristics (`_prefer_readability`); if the result is still "unclean" or shorter than `min_extracted_size`, run a third (jusText-style) and accept it only if it adds text (or the page was unclean and the size ratio holds). Then hard gates: min output size, tree size cap, language check, duplicate test. In balanced mode a short, low-coverage extraction is retried in recall mode.
8. **HTML to markdown** [read `apps/api/src/lib/html-to-markdown.ts`, `crawl4ai/markdown_generation_strategy.py`]. firecrawl: three-level fallback (HTTP service -> native Go lib -> Turndown + GFM tables), then a post-process pass (multi-line link repair etc.). crawl4ai emits three artefacts per page: `raw_markdown`, `markdown_with_citations` (each inline link replaced by `text⟨n⟩` plus a numbered References footer; one regex handles nested brackets and image links), and `fit_markdown` (markdown of the pruned HTML only).
9. **Crawl frontier** [read `scraper/WebScraper/crawler.ts`, `crawl4ai/deep_crawling/bfs_strategy.py`]. Fetch robots.txt once, honour allow + crawl-delay; seed from sitemap. Per-link filter returns an explicit denial reason enum (depth limit, include/exclude regex, robots, backward-crawl outside the start path, external domain, subdomain). Defaults: limit 10 000, depth 10, no backward/external/subdomain. crawl4ai BFS adds a filter chain, a URL scorer with threshold, `max_pages`, and `resume_state`/`on_state_change` hooks so a crawl can be checkpointed.
10. **Dedupe** [read `lib/crawl-redis.ts`, `trafilatura/deduplication.py`]. URL level: normalise (optionally drop query; drop `#fragment` unless it is a `#/` or `#!/` route) then generate permutations (www/non-www, http/https, index file) and lock all of them in a set. Content level: Simhash over sampled tokens with an LRU (4096) of seen fingerprints.
11. **Politeness** [read `crawl4ai/async_dispatcher.py` `RateLimiter`]. Per-domain state: delay starts at uniform(1,3)s; on 429/503 delay = min(delay x 2 x jitter(0.75-1.25), 60s) and fail after 3 strikes; on success delay decays x0.75 down to the base. Dispatcher also pauses admission at 90% memory, hard-stops at 95%, resumes at 85%, and bumps priority of URLs waiting > 10 min.
12. **Caching** [read `engines/index/index.ts`, `crawl4ai/cache_validator.py`]. firecrawl keys the cache on hash(normalised URL) plus render-affecting options (mobile, ad-block, location) and serves if age <= `maxAge`. crawl4ai revalidates: HEAD with If-None-Match/If-Modified-Since -> 304 = fresh; on 200 fetch only `<head>` and compare a fingerprint of key meta tags.
13. **Structured extraction** [read `crawl4ai/extraction_strategy.py`]. Two modes: (a) CSS/XPath schema = `baseSelector` + `fields[]`, no LLM, with validation feedback when the base selector matches 0 elements; (b) LLM: chunk markdown by token threshold with an overlap rate, extract per chunk against a JSON schema, merge.

### What makes it good
- Engines are data (feature map + quality), so adding a fetcher never touches control flow.
- The staggered race bounds latency without wasting the slow engine's work.
- "Is this result good?" is decided on the *converted markdown*, not on HTTP status.
- Three independent extractors with a length/cleanliness arbiter beat any single heuristic (trafilatura).
- Every rejected URL carries a human-readable reason - crawl behaviour is debuggable.
- Citation-style markdown shrinks tokens and gives the LLM stable reference ids.

### Minimum faithful re-implementation (~450 lines, stdlib + httpx + pydantic)
Keep: `Engine` table with features+quality (httpx fetch; optional hook for an external renderer); staggered race with `asyncio.wait(FIRST_COMPLETED)`; markdown-based success test + block-page regex tiers; `html.parser`-based DOM -> selector strip -> density-score pruning -> a small markdown emitter (headings, lists, links, code, tables); `urllib.robotparser` + sitemap XML; BFS frontier with reason-coded filters; URL normalisation + permutation set; per-domain adaptive delay; sqlite cache with ETag revalidation; schema extraction via one LLM call validated by pydantic.
Drop: stealth proxies, browser actions, PDF/DOCX engines, memory-adaptive dispatcher, simhash (use sha256 of normalised text first), CSS-schema auto-generation.

### Beyond them
- Write each fetch attempt (engine, status, bytes, verdict, denial reason) to the append-only audit ledger; a crawl becomes replayable evidence, and the content hash in the ledger doubles as the dedupe key.
- Run the deterministic permission check *before* the frontier enqueues a URL (domain allow-list, robots, data-classification), so policy is enforced at one choke point instead of per engine.
- Tag every markdown block with provenance (URL, fetch time, extractor that produced it) so capability 6 can treat it as untrusted data by construction.

---

## 2. LLM council / multi-model deliberation

| Repo | Stars | Licence (SPDX) | Copyleft? | Last push |
|---|---|---|---|---|
| karpathy/llm-council | 26.4k | **none (no LICENSE file)** | **all rights reserved - ideas only** | 2025-11-22 |
| togethercomputer/MoA | 3.0k | Apache-2.0 | no | 2025-01-07 |
| composable-models/llm_multiagent_debate | 0.6k | **none** | ideas only | 2025-04-24 |
| Skytliang/Multi-Agents-Debate | 0.6k | GPL-3.0 | **YES** [not read] | 2025-12-16 |

### How it works
1. **Council, stage 1 - independent answers** [read `backend/council.py`, `backend/openrouter.py`]. Send the raw user query to N models in parallel (`asyncio.gather`, 120 s timeout each). A failed model returns `None` and is silently dropped; if all fail, return an error result.
2. **Stage 2 - anonymised peer review.** Label surviving answers "Response A/B/C..." and keep `label_to_model` server-side. Each council model (including the authors of the answers) receives the question plus all labelled answers and a prompt whose role is: critique each response individually, then end with a strictly formatted `FINAL RANKING:` numbered list of labels only.
3. **Ranking parse.** Split on the `FINAL RANKING:` marker; regex for `N. Response X`; fall back to any `Response X` in order of appearance, first within the section then in the whole text.
4. **Aggregation.** For each model collect the positions it received from every reviewer; score = mean position (lower is better), also report how many rankings counted. Sort ascending. This is mean-rank (Borda-like); it is computed for display/metadata only.
5. **Stage 3 - chairman synthesis.** One designated model gets the question, all stage-1 answers *with real model names*, and all stage-2 review texts, with the role: synthesise one answer, weighing the rankings and the patterns of agreement/disagreement. Chairman failure returns a fixed error string.
6. **MoA variant** [read `advanced-moa.py`, `utils.py`]. Layered refinement instead of ranking: layer 1 = N proposers answer independently; each later layer = every proposer answers again with *all* previous-layer answers injected into the system prompt as a numbered list under an "aggregate and critically evaluate, some may be wrong" instruction; a final aggregator model does the same once and streams. Retries with 1/2/4 s backoff on rate limits; references that came back `None` are filtered.
7. **Debate variant** [read `gsm/gen_gsm.py`]. 3 agents x 2 rounds: each round every agent sees the other agents' latest answers and is asked to update its own. No judge; the final answers are compared externally.

### What makes it good
- Anonymising before review removes brand/self-preference from the ranking; de-anonymising only happens client-side.
- Forcing free-text critique *before* the ranking gives the ranking a reasoning trace and makes parsing robust (marker + two fallbacks).
- Graceful degradation everywhere: the council continues with whoever answered.
- MoA's insight: models are better at improving on others' drafts than at answering cold, so even weak proposers add value.
- **Gaps (read, not inferred):** disagreement is *not measured* in any of the three - the chairman is merely told to "consider" it; there are no cost controls beyond timeouts and MoA's `max_tokens=512` on intermediate layers; the aggregate ranking is not fed to the chairman as numbers.

### Minimum faithful re-implementation (~300 lines)
Keep: provider-agnostic `ask(model, messages) -> str | None`; parallel stage 1; label shuffle + mapping; review prompt with a machine-parsable tail; tolerant parser; mean-rank aggregation; chairman call; a pydantic `CouncilResult` holding all three stages + mapping. Optional `layers` parameter gives MoA for free (stage 1 repeated with references injected).
Drop: web UI, conversation storage, title generation, streaming.

### Beyond them
- **Measure disagreement and use it as a gate:** Kendall's W (or mean pairwise Spearman) over the reviewers' rankings plus pairwise answer similarity. High agreement after stage 1 -> skip stages 2-3 and return the top answer (big cost cut); low agreement -> escalate to an extra debate round or to human approval.
- **Deterministic budget:** estimate tokens per stage up front, check against the permission/budget engine, and record model, tokens, cost and each ranking in the audit ledger so a decision can be re-derived later.
- Shuffle labels per reviewer (kills position bias), exclude self-votes when aggregating, and have reviewers return a pydantic-validated JSON ranking with one repair retry instead of regex.

---

## 3. Long-term agent memory

| Repo | Stars | Licence (SPDX) | Copyleft? | Last push |
|---|---|---|---|---|
| mem0ai/mem0 | 68.8k | Apache-2.0 | no | 2026-11-06 |
| getzep/graphiti | 32.7k | Apache-2.0 | no | 2026-11-11 |
| letta-ai/letta (V1 server on `archive` branch; active code moved to letta-ai/letta-code, 3.8k, Apache-2.0) | 25.4k | Apache-2.0 | no | 2026-10-18 |
| topoteretes/cognee | 33.2k | Apache-2.0 | no | 2026-11-11 [not read] |

### How it works
**mem0 current pipeline ("V3 additive", ADD-only)** [read `mem0/memory/main.py` `_add_to_vector_store`, `mem0/configs/prompts.py`, `mem0/utils/scoring.py`]
1. Scope = (user_id, agent_id, run_id). Load the last 10 raw messages of the session from sqlite; embed the new messages; vector-search the top 10 existing memories in scope.
2. Map existing memory UUIDs to small integers ("0","1",...) before showing them to the LLM, and map back afterwards (prevents hallucinated UUIDs).
3. One JSON-mode LLM call. Prompt role: evidence-bound extractor whose only operation is ADD; emit self-contained 15-80 word facts, resolve relative dates against an *observation date* (not today's date), link each new fact to related existing memory ids, attribute to speaker, "when in doubt, extract - dedupe happens downstream".
4. Parse (strip code fences, tolerant JSON); batch-embed; drop any fact whose md5(text) equals an existing or in-batch hash; insert with payload {data, hash, lemmatised text for BM25, created_at, attributed_to}. Batch insert falls back to per-record insert; each persisted record gets an ADD row in a history table.
5. Extract entities from each new memory (NLP, no LLM); upsert into a separate entity collection: exact normalised-text match or cosine >= 0.95 merges, appending the memory id to `linked_memory_ids`.
6. **Search:** over-fetch `max(4k, 60)` semantic hits + BM25 keyword hits; squash BM25 with a sigmoid whose midpoint/steepness depend on query length (<=3 terms: 5.0/0.7 ... >15 terms: 12.0/0.5); entity boost = similarity x 0.5 x 1/(1+0.001(n-1)^2) where n = memories linked to that entity (damps hub entities), entity match needs sim >= 0.5; final = (semantic + bm25 + entity) / max_possible, where the semantic score must pass the threshold *before* fusion; expired payloads filtered.
7. **Legacy decision pipeline** (prompt still present as `DEFAULT_UPDATE_MEMORY_PROMPT`): two calls - extract facts, then a memory-manager prompt compares facts with retrieved memories and returns per-item events ADD / UPDATE (keep id, new text, old text) / DELETE (contradiction) / NONE (already present or irrelevant).

**graphiti temporal knowledge graph** [read `graphiti_core/graphiti.py` `add_episode`, `utils/maintenance/edge_operations.py`, `dedup_helpers.py`, `search/search_utils.py`]
8. Episode (text/message/JSON + `reference_time`) -> fetch recent previous episodes as context -> LLM extracts entity nodes -> resolve against existing nodes -> LLM extracts fact edges (source, target, fact sentence, `valid_at`, `invalid_at`) -> resolve edges -> summarise node attributes -> save episode + MENTIONS edges -> optionally update communities.
9. Node dedupe is deterministic first: exact normalised name; else if the name has enough Shannon entropy (>= 1.5, length >= 6 or >= 2 tokens) use 3-gram shingles + MinHash (32 permutations, bands of 4) LSH with Jaccard >= 0.9; only low-entropy/ambiguous names go to the LLM.
10. Edge resolution: exact normalised-fact match between the same node pair = duplicate (fast path); otherwise hybrid-search candidate edges and ask the LLM for `duplicate_facts` and `contradicted_facts` (returned indices are range-validated).
11. **Bi-temporal invalidation, never delete.** Each edge has event time (`valid_at`, `invalid_at`) and system time (`created_at`, `expired_at`). If an old edge is contradicted and its `valid_at` precedes the new edge's, set old.invalid_at = new.valid_at and old.expired_at = now; if the *new* edge is the older fact, it is the one that gets expired; non-overlapping intervals are left alone.
12. Search = BM25 + cosine + graph BFS run in parallel, fused with reciprocal rank fusion (`score += 1/(rank + 1)`), optional rerankers: MMR (lambda 0.5), node-distance from a centre node, episode-mention count, cross-encoder. Default min cosine 0.6.

**letta / MemGPT hierarchy** [read `archive` branch: `letta/functions/function_sets/base.py`, `schemas/block.py`, `services/summarizer/summarizer.py`, `constants.py`]
13. Core memory = labelled text blocks (persona, human, ...) each with a description, char limit and read-only flag, always rendered into the context window. The agent edits them itself through tools: append, exact-string replace, insert at line, apply patch, rethink (rewrite whole block).
14. Recall memory = full message log searched by tool; archival memory = vector store with insert/search tools and tags.
15. Context overflow: summarisation triggers at 90% of the context window; either static buffer (when messages exceed a limit, evict down to a minimum and summarise evicted messages in the background, fire-and-forget) or partial evict (summarise the oldest ~30%).

### What makes it good
- Integer id remapping and hash-dedupe are cheap deterministic guards around a non-deterministic extractor.
- mem0 moved from LLM-decided UPDATE/DELETE to append-only + linking: fewer destructive mistakes, one LLM call instead of two.
- Threshold-before-fusion stops keyword noise from promoting semantically irrelevant memories.
- Graphiti keeps both "when was it true" and "when did we learn it", so history queries and corrections are both answerable.
- Deterministic dedupe first, LLM only for the ambiguous residue (entropy gate).
- Letta makes memory edits ordinary tool calls, so they flow through the same approval/audit path as any tool.

### Minimum faithful re-implementation (~500 lines)
Keep: sqlite tables `memory(id, scope, text, hash, embedding, created_at, valid_at, invalid_at, expired_at, links)`, `entity(name_norm, memory_ids)`, `history`; extractor call with id remapping + observation date; md5 dedupe; contradiction check on top-k neighbours that sets `invalid_at/expired_at` instead of deleting; search = cosine (pure Python over stored vectors) + a 30-line BM25 + entity boost, RRF or the additive formula; core-memory blocks with char limits and replace/append tools; 90% context trigger with oldest-30% summarisation.
Drop: graph database, communities, cross-encoder, MinHash (exact + normalised match first), spaCy lemmatisation, 20+ vector-store adapters.

### Beyond them
- The history table *is* the audit ledger: every ADD/INVALIDATE carries the source episode id and ledger offset, giving "why does the agent believe X" for free and point-in-time recall (`as_of=`).
- Route core-memory writes and any invalidation of a high-importance fact through the deterministic permission check (and optionally human approval) - none of the references gate memory poisoning.
- Store the provenance trust level of each memory (user-stated vs. scraped web content) and exclude low-trust memories from prompts that can trigger tools (ties to capability 6).

---

## 4. Deep research agents

| Repo | Stars | Licence (SPDX) | Copyleft? | Last push |
|---|---|---|---|---|
| assafelovic/gpt-researcher | 30.6k | Apache-2.0 | no | 2026-11-09 |
| stanford-oval/storm | 31.9k | MIT | no | 2025-09-30 |
| langchain-ai/open_deep_research | 12.7k | MIT | no (repo **archived**) | 2026-08-10 |

### How it works
**open_deep_research (supervisor / sub-agent)** [read `src/open_deep_research/deep_researcher.py`, `configuration.py`]
1. `clarify_with_user` (structured output: need_clarification + question; can be disabled) -> `write_research_brief` (turn the chat into one detailed brief).
2. Supervisor loop with exactly three tools: `think_tool` (reflection, no side effect), `ConductResearch(topic)` (delegate), `ResearchComplete`. Each turn the supervisor's tool calls are executed together; at most `max_concurrent_research_units` (5) delegations run in parallel, overflow calls get an error tool message telling it to retry later.
3. Each sub-researcher is a ReAct loop (search / MCP tools / think_tool) capped at `max_react_tool_calls` (10), then a separate `compress_research` call rewrites its whole message history into a cited summary; on token-limit errors it trims history back to the last AI message and retries (3 attempts). The supervisor only ever sees the compressed result; raw notes are kept on the side.
4. Stop: `ResearchComplete`, no tool calls, or `max_researcher_iterations` (6) exceeded. Any exception in the supervisor tool step ends research gracefully with the notes gathered so far. Final report is one call over the brief + all notes. Different models per role (summarise / research / compress / final report).

**gpt-researcher (plan-and-fan-out)** [read `gpt_researcher/skills/researcher.py`, `skills/deep_research.py`, `context/compression.py`, `skills/curator.py`]
5. Initial search on the raw query -> planner LLM turns query + those results into sub-queries (the original query is appended) -> all sub-queries processed with `asyncio.gather`: search, drop already-`visited_urls`, scrape, then *embedding-filter* the scraped text (split 1000/100 chars, keep chunks with similarity >= 0.35 to the sub-query, top k) instead of LLM-summarising everything.
6. Optional source curation: an LLM ranks sources by relevance/credibility/reliability and keeps the top 10.
7. Deep mode = recursive tree: at each level generate `breadth` (4) queries each with a `researchGoal`; run each as a full researcher under a semaphore (2); an LLM extracts `learnings` (each with a source URL) and follow-up questions; recurse with depth-1 using goal + follow-ups as the next query (breadth shrinks per level [inferred from the upstream pattern; halving line not read]); stop when depth is exhausted or a level returns no successful results; context trimmed to 25 000 words.

**STORM (perspective-guided conversations)** [read `knowledge_storm/storm_wiki/modules/*.py`]
8. Persona discovery: ask for related topics, read their tables of contents, generate up to N editor personas, always prepend a "basic fact writer".
9. For each persona in parallel threads, simulate a conversation: writer-with-persona asks a question -> expert turns it into search queries (capped per turn) -> retrieves -> answers with inline citations; loop up to `max_turn` or until the writer emits the fixed thank-you sentinel.
10. Outline in two passes: draft from the model's own knowledge, then refine using the conversation transcripts (citations stripped).
11. Information table: all snippets embedded once; for each top-level section retrieve top-k snippets by cosine using the section's headings as queries; write sections in parallel (intro/conclusion skipped), each citing `[n]` local indices.
12. Citation unification: `url_to_unified_index` assigns a global number on first sight; each section's local indices are remapped; a final pre-order traversal renumbers by first appearance. A polish pass writes the lead and removes duplication.

### What makes it good
- Context isolation: sub-agents burn tokens privately and return a compressed, cited artefact - the supervisor context stays small.
- A no-op `think_tool` forces explicit reflection between searches and is nearly free.
- Embedding filtering before the LLM is the main cost control in gpt-researcher.
- Learnings carry their source URL from the moment of extraction, so citations cannot drift.
- STORM's personas produce question diversity that a single planner prompt does not.
- Every loop has a hard numeric cap plus a "return what you have" failure path.

### Minimum faithful re-implementation (~500 lines)
Keep: brief writer; supervisor loop with three pydantic tool schemas and concurrency/iteration caps; sub-researcher loop (search -> fetch via capability 1 -> relevance filter -> learnings with URLs); compression step; global `visited` set; unified citation registry (url -> index, remap on merge); section-wise report writer; partial-result return on any failure.
Drop: MCP, vector stores, websockets/progress UI, persona discovery (start with 3 fixed lenses: facts, critic, practitioner), DSPy.

### Beyond them
- Make the citation registry ledger-backed: each learning = (claim, URL, content hash of the fetched page, ledger offset). A verifier pass can then deterministically check that every `[n]` in the report maps to a stored snippet containing the claim's key terms, and flag unsupported sentences.
- Budget-aware stop condition: stop when the marginal new-learning rate (novel learnings / tokens spent) falls below a threshold, not only on fixed depth.
- Human approval interrupt (capability 5) after the brief and after the outline - the two cheap points where a correction saves the most spend.

---

## 5. Agent orchestration with durable state and human approval

| Repo | Stars | Licence (SPDX) | Copyleft? | Last push |
|---|---|---|---|---|
| langchain-ai/langgraph | 44.8k | MIT | no | 2026-11-11 |
| openai/openai-agents-python | 30.6k | MIT | no | 2026-11-11 |
| pydantic/pydantic-ai | 21.1k | MIT | no | 2026-11-11 (docs only read) |
| crewAIInc/crewAI | 60.8k | MIT | no | 2026-11-11 [not read] |
| temporalio/samples-python | 0.4k | MIT | no | 2026-11-04 [not read] |

### How it works
**langgraph (Pregel-style super-steps)** [read `libs/checkpoint/langgraph/checkpoint/base/__init__.py`, `libs/langgraph/langgraph/pregel/_algo.py`, `pregel/_loop.py`, `types.py`]
1. State lives in named **channels**; each has a value and a monotonically increasing version. A node subscribes to trigger channels. Checkpoint = `{v, id (sortable), ts, channel_values, channel_versions, versions_seen{node -> {channel -> version}}, updated_channels}`.
2. **Plan:** a node is runnable when any trigger channel's version is newer than what that node recorded in `versions_seen`. Dynamic fan-out (`Send`) creates extra "push" tasks. Task ids are deterministic hashes of (checkpoint, path), so a replay produces the same ids.
3. **Execute** all runnable tasks of the step in parallel; they see the same snapshot and cannot see each other's writes.
4. **Apply writes:** record versions seen, group writes by channel, apply through the channel's reducer (e.g. append vs. overwrite), bump versions; this defines the next step's runnable set. Loop until no tasks or the step limit (`out_of_steps`).
5. **Durability:** as each task finishes, its writes are saved as *pending writes* keyed by (checkpoint id, task id) (`put_writes`); the full checkpoint is saved after the step. On resume, tasks with saved writes are not re-run - only failed/unfinished ones. Durability mode can defer persistence to exit.
6. **Interrupts:** static (`interrupt_before/after` node lists, checked against versions seen by a pseudo-node) and dynamic: `interrupt(value)` inside a node raises a GraphInterrupt carrying the payload; state is checkpointed; the caller resumes with `Command(resume=x)`; **the node re-executes from its top** and the i-th `interrupt()` call returns the i-th stored resume value (counter in a per-task scratchpad). Code before an interrupt must therefore be idempotent. Requires a checkpointer.
7. Threads: checkpoints are chained by `parent_config` per `thread_id`, enabling history listing, time travel and forking.

**openai-agents-python (turn loop + approvals)** [read `src/agents/run.py`, `run_internal/run_steps.py`, `run_internal/approvals.py`, `run_state.py`, `guardrail.py`, `docs/human_in_the_loop.md`]
8. Turn = one model call; the response is sorted into a `ProcessedResponse` (function calls, handoffs, shell/patch/computer calls, MCP approval requests, tools-not-found, interruptions). The step outcome is one of four types: FinalOutput, Handoff(new_agent), RunAgain, Interruption. Loop until final output or `max_turns`.
9. Handoffs are exposed to the model as tools; taking one swaps the current agent and continues the same loop with the history (optionally filtered).
10. Guardrails: input guardrails run on the first agent's input, by default *in parallel* with the model call (so a trip can cancel it; `run_in_parallel=False` makes them blocking); output guardrails run on the final output; each returns `{output_info, tripwire_triggered}` and a trip raises a typed exception. Tool-level input/output guardrails also exist.
11. Approval: a tool declares `needs_approval` = bool or async predicate(ctx, params, call_id). The predicate **fails closed** when arguments are missing/malformed/non-object JSON. If approval is needed and no decision is stored, the run returns with `interruptions` (ToolApprovalItem: agent, tool name, arguments). The caller converts the result to a `RunState`, calls `approve(item)` / `reject(item)` (optionally sticky "always"), serialises it if needed (versioned schema, currently 1.22), and re-enters `Runner.run(agent, state)`. A rejection is fed back to the model as a synthetic tool output. Sticky approvals for function tools are scoped to the requesting agent; the docs warn that shell/patch sticky approvals are not.
12. **pydantic-ai** [read `docs/deferred-tools.md`]: a tool raises ApprovalRequired/CallDeferred; the run ends with a `DeferredToolRequests` output; the caller builds `DeferredToolResults` (approve / `ToolDenied` / external result per call id) and starts a new run with the original message history.

### What makes it good
- Version-based scheduling makes the graph a pure function of the checkpoint - resumable anywhere, no separate scheduler state.
- Pending writes give task-level (not just step-level) recovery, so a crashed parallel step does not redo completed siblings.
- Interrupt-as-exception + replay needs no coroutine serialisation; the price (re-execution) is explicit and documented.
- Reducers per channel resolve concurrent writes deterministically.
- A small closed set of "next step" types keeps the agent loop auditable.
- Approval state is data (serialisable, versioned), so a pause can outlive the process.

### Minimum faithful re-implementation (~450 lines)
Keep: `Channel(value, version, reducer)`; nodes with trigger sets; `plan -> run (asyncio.gather) -> apply_writes -> checkpoint` loop with a step cap; sqlite checkpointer with `checkpoints(thread, id, parent, blob)` and `writes(thread, checkpoint_id, task_id, channel, value)`; deterministic task ids (sha256 of checkpoint id + node + trigger versions); `interrupt()` via exception + indexed resume list; `Command(resume=...)`; on top of it a tool-call loop node with `needs_approval` predicates (fail closed), handoff-as-tool, and pre/post guardrail hooks returning a tripwire flag.
Drop: subgraphs, streaming modes, `Send` fan-out (add later), caching, sessions, tracing, MCP.

### Beyond them
- Checkpoints as ledger entries: each checkpoint stores the hash of its parent, so the thread history is a tamper-evident chain and "who approved what, seeing which arguments" is provable.
- Replace the per-tool predicate with the platform's deterministic permission check as the *single* authority: result = allow | deny | require_approval(role). The model can never widen it, and sticky approvals become explicit, scoped, expiring grants in the ledger.
- Memoise side-effecting calls made before an `interrupt()` by (task id, call index) in the writes table, removing the "code before interrupt must be idempotent" foot-gun.

---

## 6. Guardrails and prompt-injection defence

| Repo | Stars | Licence (SPDX) | Copyleft? | Last push |
|---|---|---|---|---|
| NVIDIA-NeMo/Guardrails | 7.5k | Apache-2.0 (LICENSE read; GitHub reports NOASSERTION) | no | 2026-11-11 |
| google-research/camel-prompt-injection | 0.4k | Apache-2.0 | no (research artefact, unmaintained by its own README) | 2025-06-20 |
| meta-llama/PurpleLlama (LlamaFirewall) | 4.5k | repo root: Llama community licence; `LlamaFirewall/LICENSE`: MIT | no; **model weights have separate terms** | 2026-11-09 |
| protectai/llm-guard | 3.2k | MIT | no (**archived**) | 2026-07-08 |
| protectai/rebuff | 1.5k | Apache-2.0 | no (**archived**) | 2024-08-07 |

### How it works
**Detection layers**
1. **Scanner chain (llm-guard)** [read `llm_guard/evaluate.py`]. Each scanner: `scan(text) -> (sanitised_text, is_valid, risk_score)`. Scanners run in order, each receiving the previous scanner's sanitised output; results are collected per scanner; `fail_fast` stops at the first invalid. Output scanners additionally receive the prompt.
2. **Classifier scanner** [read `input_scanners/prompt_injection.py`]. Fine-tuned DeBERTa classifier, threshold 0.92, 512-token window; long inputs handled by a match strategy: full, per sentence, word chunks, or head+tail truncation; the max score over pieces decides.
3. **Heuristic + vector + LLM + canary (rebuff)** [read `python-sdk/rebuff/sdk.py`, `detect_pi_heuristics.py`]. Heuristic: generate every verb x adjective x object x preposition phrase ("ignore ... previous ... instructions"), slide a same-length word window over the normalised input, score 0.5 + 0.5 x matched-word fraction, take the max. Three independent scores with thresholds 0.75 heuristic / 0.90 vector similarity to known attacks / 0.90 LLM judge; any exceedance = injection. Canary: random hex token placed in the prompt; if it appears in the output, the prompt leaked (and the attack can be stored for the vector layer [inferred]).
4. **Invisible-text scanner** [read `input_scanners/invisible_text.py`]: strip Unicode categories Cf/Co/Cn (zero-width, private use, unassigned).
5. **Perplexity heuristics (NeMo)** [read `nemoguardrails/library/jailbreak_detection/heuristics/checks.py`]: length/perplexity >= 89.79, or perplexity of the first/last ~20 words >= 1845.65, flags adversarial-suffix jailbreaks (needs a small LM).
6. **Five rail positions (NeMo)** [read README]: input rails (reject/alter user input), dialog rails (constrain what the LLM is asked next), retrieval rails (reject/alter RAG chunks), execution rails (around tool input/output), output rails. Library includes self-check prompts (LLM judges input/output/facts), YARA-rule injection detection, regex, sensitive-data detection.
7. **LlamaFirewall** [read `LlamaFirewall/README.md`]: PromptGuard (small BERT-style classifier on user input *and* untrusted tool/web content), AlignmentCheck (a second LLM audits the agent's reasoning trace against the user's goal to catch goal hijacking), regex/custom scanners, CodeShield (static analysis of generated code via Semgrep/regex rules).

**Privilege separation (CaMeL)** [read `src/camel/capabilities/*.py`, `security_policy.py`, `quarantined_llm.py`, `pipeline_elements/privileged_llm.py`]
8. **Privileged LLM** sees only the trusted user request and tool signatures and writes a *program* (restricted Python). It never sees tool outputs.
9. A custom **interpreter** runs the program. Every value carries `Capabilities{sources, readers}`: sources in {User, CaMeL, Assistant, TrustedToolSource, Tool(name, inner_sources)}; readers = Public or a set of principals. Values derived from others inherit their dependencies [inferred from `check_policy(tool, kwargs, dependencies)`; `interpreter/value.py` not read].
10. **Quarantined LLM** = `query_ai_assistant(query, output_schema)`: parses untrusted text into a pydantic schema, has no tools, and must set `have_enough_information`; false raises NotEnoughInformationError.
11. **Policy check before every tool call:** no-side-effect tools always allowed; a state-changing tool whose dependencies include any non-public value is denied; otherwise the first policy whose glob matches the tool name decides; **no matching policy = deny**. Per-tool policies inspect argument capabilities.
12. Errors go back to the privileged LLM for repair (up to 10 attempts), but exception text originating from untrusted data is **redacted** so it cannot act as an injection channel.
13. **Rule of Two** [NOT read this session - recalled from Meta's 2025 guidance; verify before relying on it]: within one session an agent should hold at most two of (a) processing untrusted input, (b) access to sensitive data/systems, (c) ability to change state or communicate externally; all three requires human approval.

**PII** [read `input_scanners/anonymize.py`]
14. Detect entities (NER + regex), resolve overlapping spans, replace with `[REDACTED_TYPE_n]`, store placeholder -> original in a vault; an output scanner de-anonymises the model's answer.

### What makes it good
- Layers are independent and cheap-first; any single layer may veto.
- Scanners sanitise as well as judge, so redaction and blocking share one pipeline.
- CaMeL does not try to *detect* injections: untrusted text can never choose which tool runs, only fill typed slots, and data-flow labels stop exfiltration through arguments.
- Default-deny for unmatched tools and fail-closed on missing information.
- Redacting untrusted exception text closes a side channel most designs miss.
- AlignmentCheck audits the trajectory, catching hijacks no input classifier sees.

### Minimum faithful re-implementation (~450 lines)
Keep: `Scanner` protocol + chain with fail-fast; invisible-char stripper; combinatorial phrase heuristic; regex/secret patterns; optional LLM-judge scanner; canary tokens; PII vault with regex recognisers (email, phone, card + Luhn, IBAN, API-key shapes) and reversible placeholders; a `Tainted[T]` wrapper carrying sources/readers that propagates through tool results; quarantined-extraction function (schema-only output, no tools, `enough_information` flag); pre-tool policy check with default deny; redaction of untrusted error text.
Drop: ML classifiers and perplexity models (pluggable later), Colang dialog rails, a full Python-subset interpreter (use a JSON plan of tool steps with variable references instead), CodeShield.

### Beyond them
- The platform's deterministic permission check *is* the CaMeL policy engine: feed it (tool, argument taint labels, session trust state) and log every decision to the ledger; taint labels are persisted with the data (capabilities 1, 3, 7), not just in-memory.
- Enforce the Rule of Two mechanically: track three session bits, and when the third would flip, emit a human-approval interrupt (capability 5) instead of relying on prompt discipline.
- Feed confirmed attacks from the ledger back into the heuristic/vector layer automatically (self-hardening), with canary hits as ground truth.

---

## 7. Document ingestion / parsing for knowledge bases and RAG

| Repo | Stars | Licence (SPDX) | Copyleft? | Last push |
|---|---|---|---|---|
| microsoft/markitdown | 194.9k | MIT | no | 2026-11-07 |
| docling-project/docling (+ docling-core, MIT) | 70.4k | MIT | no | 2026-11-11 |
| HKUDS/LightRAG | 40.6k | MIT | no | 2026-11-11 |
| microsoft/graphrag | 36.6k | MIT | no | 2026-11-09 |
| infiniflow/ragflow | 94.0k | Apache-2.0 | no | 2026-11-11 [not read] |
| Unstructured-IO/unstructured | 15.7k | Apache-2.0 | no | 2026-11-06 [not read] |

### How it works
1. **Converter registry (markitdown)** [read `packages/markitdown/src/markitdown/_markitdown.py`]. Converters register with a priority (0 = specific formats, 10 = generic text/HTML/zip). For an input, build several `StreamInfo` guesses (extension, mimetype, charset from the caller, HTTP headers, and content sniffing via magika). For each guess, for each converter in priority order: `accepts(stream, info)` -> `convert(...)`; the stream position is restored after every attempt; failures are collected; if none succeed raise UnsupportedFormat, or FileConversion with the list of failed attempts.
2. **Layout-aware PDF pipeline (docling)** [read `docling/pipeline/standard_pdf_pipeline.py`]. Stages: preprocess (render page) -> OCR -> layout detection -> table structure -> page assembly -> reading order. Each stage is one worker thread with a *bounded* input queue and batch-get with timeout; producers block when the queue is full (back-pressure); queues have explicit close semantics; each run gets its own queues. Output is a typed document tree (headings, paragraphs, lists, tables, pictures with captions, provenance).
3. **Hierarchical chunking (docling-core)** [read `transforms/chunker/hierarchical_chunker.py`]. Walk the document in order keeping `heading_by_level`; emit one chunk per element with metadata = current heading path + captions + source items. Tables are serialised as triplets "row header, column header = value" so each cell is self-describing.
4. **Hybrid chunking** [read `transforms/chunker/hybrid_chunker.py`]. Token-aware refinement, where token count is measured on the *contextualised* text (headings + captions + body): (a) oversized chunk -> split along document-item boundaries with a sliding window; (b) a single oversized item -> plain-text semantic split with a budget of max_tokens minus heading overhead; (c) `merge_peers`: merge consecutive undersized chunks that share identical headings; (d) repeat the table header in every piece of a split table.
5. **LightRAG indexing** [read `lightrag/operate.py` function map, `constants.py`]. Chunk -> LLM extracts entities and relationships per chunk with one extra "gleaning" pass (did you miss any?) -> merge by entity name across chunks: descriptions concatenated and de-duplicated, re-summarised by LLM only once a node has >= 8 fragments or exceeds the token budget -> upsert into a graph store and three vector indexes (entities, relationships, chunks). Source chunk ids per entity are capped (200). Extraction results are cached so the graph can be rebuilt after deletions.
6. **LightRAG query** [read `_perform_kg_search`, `base.py` QueryParam]. One LLM call extracts high-level (themes) and low-level (specific entities) keywords. `local` = vector-search entities with low-level keywords -> their edges -> their source chunks; `global` = vector-search relationships with high-level keywords -> their endpoint entities -> chunks; `hybrid` = both; `mix` (default) = both plus plain chunk vector search; `naive` = chunks only. Query, ll and hl keyword embeddings are computed in one batch. Then token-budget truncation (entities 6k, relations 8k, total 30k), optional rerank, defaults top_k 40 / chunk_top_k 20 / cosine >= 0.2.
7. **GraphRAG indexing** [read `packages/graphrag/graphrag/index/workflows/factory.py`]. Standard pipeline, in order: load documents -> base text units -> final documents -> extract graph (LLM) -> finalize graph -> extract covariates (claims) -> create communities (hierarchical clustering) -> final text units -> community reports (LLM summary per community) -> text embeddings. "Fast" variant swaps LLM extraction for NLP extraction + graph pruning and text-based reports. A separate update pipeline merges deltas.
8. **GraphRAG global search** [read `query/structured_search/global_search/search.py`]. Map: batch community reports to fit `max_data_tokens` (8000), ask the LLM (JSON mode) for scored key points per batch in parallel. Reduce: filter and rank points by score [inferred from parameter names and the NO_DATA path], fit to the token budget, synthesise; general knowledge allowed only if flagged. Other modes present: local (entity-centred mixed context), DRIFT, basic.

### What makes it good
- Try-in-priority-order with stream rewind makes format detection robust to wrong extensions.
- Chunk text is prefixed with its heading path, so an isolated chunk still says what it is about - and token limits are enforced on that final form.
- Triplet table serialisation survives arbitrary splitting.
- Bounded queues give back-pressure for free; a slow OCR stage cannot blow memory.
- Dual-level keywords let one index answer both "what is X" and "what are the themes" without community reports.
- Incremental merge (summarise only past a fragment threshold) keeps index cost linear.

### Minimum faithful re-implementation (~500 lines)
Keep: converter registry with priority + `accepts` + rewind (stdlib converters: text, HTML via capability 1, CSV, JSON, DOCX/XLSX/PPTX through `zipfile` + `xml.etree`); a typed block list (heading level, paragraph, list item, table rows, source location); heading-path chunker with token budget, peer merge and table-header repeat; triplet table serialisation; hybrid retrieval = cosine + BM25 fused by RRF; entity/relation extraction with one gleaning pass into sqlite `entity` / `relation` tables with `chunk_ids`; dual-keyword local/global/mix query with token budgets.
Drop: PDF layout models/OCR (delegate PDF to an external parser behind the registry), community detection and reports, DRIFT, reranker models, multi-store adapters.

### Beyond them
- Content-addressed ingestion: sha256 of each source file and each chunk recorded in the ledger; re-ingest becomes a diff, and every retrieved chunk can be traced to an exact file version (and its access rights re-checked at query time by the permission engine).
- Carry trust/taint labels from parser to chunk to retrieved context, so retrieval rails (capability 6) are structural rather than heuristic.
- Bi-temporal relations in the graph index (reuse capability 3) so superseded document versions invalidate, not duplicate, facts.

---

## 8. Workflow mining / process discovery and n8n-style workflow import

| Repo | Stars | Licence (SPDX) | Copyleft? | Last push |
|---|---|---|---|---|
| n8n-io/n8n | 210.1k | **Sustainable Use License 1.0** (GitHub: NOASSERTION; `.ee` files under a separate enterprise licence) | **source-available, not open source - ideas only; the JSON format itself is just data** | 2026-11-11 |
| process-intelligence-solutions/pm4py | 1.1k | AGPL-3.0 | **YES - ideas only** (algorithms are textbook) | 2026-11-05 |

### How it works
**n8n workflow JSON** [read `packages/workflow/src/interfaces.ts`, `common/map-connections-by-destination.ts`, `workflow.ts`]
1. Top level: `{id, name, active, nodes[], connections{}, settings?, staticData?, pinData?, versionId?, meta?}`.
2. Node: `{id, name (unique - the join key), type (e.g. "n8n-nodes-base.httpRequest"), typeVersion, position [x, y], parameters{}, credentials?{credType: {id, name}}, disabled?, retryOnFail?, maxTries?, waitBetweenTries?, alwaysOutputData?, executeOnce?, onError? ("stopWorkflow" | "continueRegularOutput" | "continueErrorOutput"), webhookId?}`. Credentials are **references only** (id + display name); secrets are not in the export.
3. Connections are keyed by **source node name**: `connections[source][connType][outputIndex] = [{node: targetName, type, index: targetInputIndex}, ...]` (an output slot may be `null`). `connType` is `"main"` for data flow, or `ai_*` (ai_tool, ai_languageModel, ai_memory, ai_embedding, ai_vectorStore, ...) for sub-nodes attached *to* an agent/chain node; those edges are capability attachments, not control flow.
4. Multiple output indices on one node encode branching (IF true/false, switch cases, the error output when `onError = continueErrorOutput`); multiple input indices encode merge inputs.
5. To execute/analyse: build the inverse map (by destination) in one pass, with sanity caps (input index <= 1000, total slots <= 100 000 - guards against hostile files). Start node = first enabled trigger/poll/webhook node, else a known starting type by fixed precedence. Parents/children found by BFS over the inverse/forward maps with optional depth; disabled nodes are skipped by walking through to their parents.
6. `settings.executionOrder` (v0 | v1) changes branch ordering semantics; `pinData[nodeName]` holds frozen sample outputs (useful as test fixtures); expressions inside `parameters` are strings starting with `=` containing `{{ ... }}` references to other nodes [inferred from general format knowledge; expression engine not read].

**Process mining (pm4py)** [read `pm4py/algo/discovery/dfg/variants/native.py`, `performance.py`, `pm4py/statistics/rework/log/get.py`]
7. Event log = rows of (case id, activity, timestamp[, start timestamp, resource]). Group by case and sort by time to get traces.
8. **Directly-follows graph:** `Counter((trace[i-1].activity, trace[i].activity) for i in 1..len)`; a `window` parameter generalises to follows-at-distance-k; a keep-once-per-case option counts each pair at most once per case (case frequency instead of occurrence frequency). Also record start and end activity counts.
9. **Performance DFG:** for each directly-follows pair collect duration = next.start_timestamp - previous.complete_timestamp (optionally in business hours); aggregate as mean / median / min / max / stdev / sum.
10. **Bottlenecks** [inferred - standard practice on top of step 9]: rank edges by median (or p95) wait x frequency; rank activities by service time when start and complete timestamps both exist.
11. **Rework:** per trace count activities occurring more than once; report, per activity, the number of cases with rework. Self-loops (a, a) and short loops (a, b, a) in the DFG are the structural signature.
12. Variants [inferred]: Counter of the activity tuple per case; the top-k variants usually cover most cases, the long tail marks exceptions.

### What makes it good
- Name-keyed adjacency with typed, indexed ports captures branching, merging and error paths without a separate edge table.
- Separating data-flow edges (`main`) from attachment edges (`ai_*`) is exactly the distinction needed for agent workflows.
- Credentials by reference makes exports shareable and forces an explicit re-binding step on import.
- The DFG is a single pass, order-independent across cases, trivially incremental, and already answers frequency, bottleneck and rework questions.
- Case-frequency vs. occurrence-frequency is the small switch that prevents one looping case from distorting the map.

### Minimum faithful re-implementation (~400 lines)
Keep: pydantic models `Workflow`, `Node`, `Connection` with `extra="allow"`; loader that validates unique node names, dangling connection targets and the index caps; forward + inverse adjacency; trigger detection; topological order over `main` edges with cycle detection (loops are legal in n8n - report them, do not reject); a report of node types, credential references needing re-binding, error-handling settings, disabled nodes, unreachable nodes; mapping table from n8n node type to a Velaris tool, unknown types becoming "manual step" placeholders. Mining: CSV/ledger reader -> traces -> DFG (frequency + performance) -> start/end activities -> variants -> rework -> bottleneck ranking -> DOT/Mermaid export.
Drop: expression evaluation, executing n8n nodes, pinData replay, Petri-net discovery (alpha/inductive miner), conformance checking, business-hours calendars.

### Beyond them
- The append-only audit ledger already *is* an event log (case = run/thread id, activity = tool or node name, timestamps, actor): mine it continuously to get a live DFG of how agents and humans actually work, with approval wait times as first-class bottlenecks.
- Conformance for free: compare the mined DFG with the imported/declared workflow graph; edges present in reality but not in the design are shadow process, design edges never taken are dead paths.
- On import, run every node's implied permissions (credential type + operation) through the deterministic permission check and present a single approval diff before the workflow can be activated.

---

## Coverage notes
- Read in depth: firecrawl, crawl4ai, trafilatura, llm-council, MoA, mem0, graphiti, letta (archive branch), open_deep_research, gpt-researcher, STORM, langgraph, openai-agents-python, llm-guard, rebuff, CaMeL (policy/capability layer), NeMo (README + heuristics), LlamaFirewall (README), markitdown, docling/docling-core, LightRAG, GraphRAG, n8n (workflow package), pm4py (DFG/performance/rework).
- Metadata only (stars/licence, no source opened): jina-ai/reader, mozilla/readability, cognee, crewAI, temporalio samples, RAGFlow, unstructured, Skytliang/Multi-Agents-Debate.
- Not verified from a primary source: Meta "Rule of Two" (section 6 step 13); CaMeL value-level dependency propagation; GraphRAG reduce-step ranking details; n8n expression syntax; gpt-researcher breadth halving.
- Firecrawl search credits used: 0 (all discovery done through the GitHub API).
