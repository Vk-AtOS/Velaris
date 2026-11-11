# 04. Control layer: research findings

Date of research: 2026-11-11. Scope: browser control, desktop control, record and replay, reversibility, policy engines, connectors, prompt injection against computer-use agents.

How to read this file:

- "Fetched" means the value came from the GitHub API, a LICENSE file, a README, a docs page or a leaderboard page during this session.
- "[read]" means source or docs of a permissively licensed repo were read (blobless shallow clone, files only, nothing executed).
- "[docs only]" means README or official docs only. All GPL, AGPL, source-available and unlicensed projects are docs only; none of their source was opened.
- "[memory]" means recalled, not fetched this session. Treat as unverified.
- No code from any project appears here. Mechanisms are described in prose.

Existing pieces this plugs into (read this session): `velaris/intel/flow.py` (one JSON tool call per turn; allow / approve / deny; hash-chained SQLite events; `exec` row written before the side effect; `idempotent` flag; approval bound to the hash of tool plus arguments), `velaris/intel/guard.py` (scan, wrap, redact), `aether_os/prime/authz.py` (pure `authorize`, NEVER list, autonomy levels), `aether_os/core/policy/engine.py` (outline only).

---

## 1. Verification table

Stars and dates are as returned by the GitHub API on 2026-11-11. "Licence" is the SPDX id the API returned; where the API said NOASSERTION the LICENSE file was read and its content is given.

### 1a. The sixteen named candidates

| Path | Licence as fetched | Last push | Stars | Status | Verdict |
|---|---|---|---|---|---|
| browser-use/browser-use | MIT | 2026-11-11 | 120.7k | Active. **Rewritten as 1.0**: the model now writes Python in a persistent REPL over raw CDP; default model and default browser are the vendor's paid cloud (local Chromium is opt-in). | Study the page-state and settle logic; do not adopt the code-as-action loop |
| browserbase/stagehand | MIT | 2026-11-11 | 26.0k | Active. Caching is now a vendor-side service, not local. | Study (snapshot, observe-then-act) |
| bytedance/UI-TARS-desktop | Apache-2.0 | 2026-10-09 | 39.6k | **Archived** | Skip as a dependency; papers still useful |
| simular-ai/Agent-S | Apache-2.0 | 2026-10-30 | 12.9k | Active. Current work is "Agent S4"; the installable agent is S3 (`gui_agents/s3`). | Study |
| trycua/cua | MIT, **with carve-outs**: Spaces app and driver bench are FSL-1.1-MIT (source-available); optional `cua-som` is AGPL-3.0-or-later; optional perception extension pulls an AGPL icon detector | 2026-11-11 | 32.2k | Active | Study the MIT parts only (driver, Lume) [docs only for FSL parts] |
| OpenAdaptAI/OpenAdapt | MIT | 2026-11-11 | 1.9k | Active. **Repositioned**: no longer "record and replay with a model"; now compiles one demonstration into a model-free program with read-back verification. | Study closely |
| microsoft/OmniParser | LICENSE file is **CC-BY-4.0** (README badge says MIT). README: `icon_detect_v3` weights are MIT (YOLOv9 based); earlier Ultralytics-based detectors are AGPL; caption models MIT. | 2026-07-20 | 25.6k | Not archived, quiet since July | Study the idea; check weight version before any use |
| Skyvern-AI/skyvern | **AGPL-3.0** | 2026-11-11 | 23.4k | Active | Avoid code; docs only |
| openinterpreter/open-interpreter | Path redirects to **openinterpreter/openinterpreter**; Apache-2.0 | 2026-11-11 | 68.9k | Active, but now "a coding agent for open models", a fork of OpenAI Codex in Rust. No longer a general computer-control project. | Skip for this slice |
| microsoft/playwright-mcp | Apache-2.0 | 2026-11-10 | 39.5k | Active | Study (accessibility snapshot with refs) |
| anthropics/claude-quickstarts | MIT | 2026-11-06 | 20.7k | Active | Study as the reference screenshot loop [memory for contents; not re-read] |
| cedar-policy/cedar | Apache-2.0 | 2026-11-11 | 1.9k | Active | Study the model |
| open-policy-agent/opa | Apache-2.0 | 2026-11-11 | 12.5k | Active | Study the model |
| openfga/openfga | Apache-2.0 | 2026-11-11 | 6.1k | Active | Study the model |
| activepieces/activepieces | **Mixed**: MIT, except `packages/ee/` and `packages/server/api/src/app/ee`, which are under a separate enterprise licence | 2026-11-11 | 25.5k | Active | Study the piece framework (MIT part) |
| temporalio/temporal | MIT | 2026-11-11 | 24.3k | Active | Study the saga pattern only; already covered by the earlier brief |

### 1b. Further repos checked

| Path | Licence as fetched | Last push | Stars | Status | Verdict |
|---|---|---|---|---|---|
| **Browser** | | | | | |
| microsoft/playwright | Apache-2.0 | 2026-11-11 | 99.9k | Active | Study (trace, codegen, aria snapshot) |
| vercel-labs/agent-browser | Apache-2.0 | 2026-11-11 | 49.7k | Active | Study (snapshot refs, fail-not-succeed clicks) |
| ChromeDevTools/chrome-devtools-mcp | Apache-2.0 | 2026-11-11 | 55.1k | Active | Study |
| browser-use/browser-harness | MIT | 2026-11-11 | 19.0k | Active | Study (attaches to the user's own Chrome) |
| nanobrowser/nanobrowser | Apache-2.0 | 2026-11-10 | 14.3k | Active | Optional |
| steel-dev/steel-browser | Apache-2.0 | 2026-11-09 | 7.9k | Active | Optional (browser sandbox) |
| kernel/kernel-images | Apache-2.0 | 2026-11-11 | 1.1k | Active | Optional (browser sandbox) |
| web-infra-dev/midscene | MIT | 2026-11-11 | 15.6k | Active | Optional (vision-first web) |
| microsoft/magentic-ui | MIT | 2026-09-23 | 10.1k | Not archived | Study the co-planning and approval UI |
| microsoft/fara | MIT | 2026-09-22 | 6.3k | Not archived | Optional (small local CUA model; weight licence not checked) |
| alumnium-hq/alumnium | MIT | 2026-11-10 | 1.0k | Active | Study (2nd on a third-party WebVoyager board) |
| magnitudedev/browser-agent | Apache-2.0 | 2026-02-08 | 4.1k | Quiet since Feb | Optional |
| cuga-project/cuga-agent | Apache-2.0 | 2026-11-11 | 1.1k | Active | Optional (enterprise API plus web hybrid) |
| browserable/browserable | MIT | 2025-08-27 | 1.2k | Stale | Skip |
| hcompai/surfer-h-cli | BSD-3-Clause | 2026-06-25 | 0.2k | **Archived** | Skip |
| hyperbrowserai/HyperAgent | NOASSERTION (file not read) | 2026-05-11 | 1.6k | Unknown | Skip |
| lightpanda-io/browser | **AGPL-3.0** | 2026-11-11 | 41.9k | Active | Avoid code |
| browseros-ai/BrowserOS | **AGPL-3.0** | 2026-11-11 | 14.3k | Active | Avoid code |
| ServiceNow/BrowserGym | Apache-2.0 (LICENSE read; API says NOASSERTION) | 2026-11-09 | 1.4k | Active | Use as an evaluation harness idea |
| web-arena-x/webarena | Apache-2.0 | 2025-11-26 | 1.6k | Quiet | Benchmark reference |
| **Desktop** | | | | | |
| vercel-labs/agent-desktop | Apache-2.0 | 2026-11-11 | 21.9k | Active; new in 2026 | Study (accessibility tree on macOS, Windows, Linux; snapshot-scoped refs) |
| agent-sh/computer-use-linux | MIT | 2026-11-11 | 0.8k | Active; new in 2026 | Study (AT-SPI, Wayland input, post-action verification) |
| agent-sh/agent-workspace-linux | MIT | 2026-11-09 | 0.2k | Active | Optional (hidden agent desktop) |
| openclaw/Peekaboo (was steipete/Peekaboo) | MIT | 2026-11-08 | 5.5k | Active | Study (macOS AX plus screenshots) |
| microsoft/UFO | MIT | 2026-10-30 | 10.2k | Active | Study (Windows UIA, hybrid GUI plus API) |
| CursorTouch/Windows-MCP | MIT | 2026-11-11 | 11.5k | Active | Optional (Windows) |
| pywinauto/pywinauto | BSD-3-Clause | 2026-11-08 | 6.4k | Active | Reference for Windows UIA from Python |
| QwenLM/open-computer-use | Apache-2.0 | 2026-11-09 | 0.3k | Active | Optional |
| ghostwright/ghost-os | MIT | 2026-03-23 | 1.7k | Quiet since March | Optional (macOS, no screenshots, learned workflows) |
| askui/python-sdk | MIT | 2026-10-26 | 0.6k | Active | Optional |
| bytedance/UI-TARS | Apache-2.0 | 2026-01-27 | 11.7k | **Archived** | Papers only |
| showlab/ShowUI | Apache-2.0 | 2026-04-24 | 1.9k | Quiet | Optional (grounding model) |
| xlang-ai/OpenCUA | MIT | 2026-05-25 | 0.9k | Quiet | Optional |
| meituan/EvoCUA | Apache-2.0 | 2026-03-31 | 0.4k | Quiet | Optional (on the official OSWorld list) |
| Tongyi-MAI/OpenGCUA | Apache-2.0 | 2026-10-26 | 0.6k | Active | Optional |
| X-PLUG/MobileAgent | MIT | 2026-11-03 | 9.4k | Active | Out of scope (mobile) |
| zai-org/Open-AutoGLM | Apache-2.0 | 2026-03-06 | 26.6k | Quiet | Out of scope (mobile) |
| droidrun/mobilerun (was droidrun/droidrun) | MIT | 2026-11-11 | 10.0k | Active | Out of scope (mobile) |
| minitap-ai/mobile-use | Apache-2.0 | 2026-11-11 | 3.4k | Active | Out of scope (mobile) |
| browser-use/macOS-use | MIT | 2025-03-05 | 2.0k | **Archived** | Skip |
| mediar-ai/terminator | MIT | 2026-06-02 | 1.7k | Quiet | Skip |
| xlang-ai/OSWorld | Apache-2.0 | 2026-11-10 | 3.3k | Active | Benchmark reference |
| google-research/android_world | Apache-2.0 | 2026-11-10 | 1.0k | Active | Benchmark reference |
| microsoft/WindowsAgentArena | MIT | 2026-10-26 | 0.9k | Active | Benchmark reference |
| google-gemini/computer-use-preview | Apache-2.0 | 2026-07-28 | 3.3k | Quiet | Optional reference loop |
| openai/openai-cua-sample-app | MIT | 2026-10-19 | 1.9k | Active | Optional reference loop |
| **Sandboxes and VMs** | | | | | |
| lima-vm/lima | Apache-2.0 | 2026-11-11 | 22.3k | Active | Use as the permissive VM route on macOS |
| e2b-dev/desktop | Apache-2.0 | 2026-11-11 | 1.6k | Active | Study (cloud desktop; not local-first) |
| e2b-dev/E2B | Apache-2.0 | 2026-11-11 | 14.8k | Active | Optional |
| e2b-dev/open-computer-use | Apache-2.0 | 2026-10-23 | 2.4k | Active | Optional |
| anthropics/sandbox-runtime (was anthropic-experimental/) | Apache-2.0 | 2026-11-11 | 7.1k | Active | Study (OS-level process sandbox for the shell tool) |
| dockur/windows | MIT | 2026-11-02 | 54.2k | Active | Optional (Windows in a container) |
| dagger/container-use | Apache-2.0 | 2026-09-21 | 4.1k | Not archived | Study (container plus git branch per agent) |
| openai/tart (was cirruslabs/tart) | **FSL-1.1-ALv2** (source-available) | 2026-11-06 | 7.9k | Active | Avoid code; use Lima or the MIT Lume part of cua |
| daytonaio/daytona | **No licence file found**; **archived** | 2026-07-24 | 71.3k | Archived | Avoid |
| **Record and replay** | | | | | |
| rrweb-io/rrweb | MIT | 2026-11-11 | 20.4k | Active | Study (DOM mutation recording) |
| puppeteer/replay | Apache-2.0 | 2026-11-02 | 1.4k | Active | Study (JSON recording format with selector fallbacks) |
| aisingapore/TagUI | Apache-2.0 | 2026-11-08 | 6.3k | Active | Optional |
| robocorp/rpaframework | Apache-2.0 | 2026-11-02 | 1.6k | Active | Optional |
| showlab/ShowUI-Aloha | Apache-2.0 | 2026-01-20 | 0.3k | Quiet | Optional (human-taught desktop agent) |
| browser-use/workflow-use | **AGPL-3.0** | 2026-11-06 | 4.3k | Active | Avoid code |
| AutomaApp/automa | **AGPL** plus a commercial licence for the `business` directory | 2026-03-02 | 21.7k | Quiet | Avoid code |
| screenpipe/screenpipe (was mediar-ai/screenpipe) | **"Screenpipe Commercial License"** (not open source) | 2026-11-11 | 22.3k | Active | Avoid |
| **Reversibility and coding agents** | | | | | |
| jj-vcs/jj | Apache-2.0 | 2026-11-11 | 32.5k | Active | Study the operation log |
| cline/cline | Apache-2.0 | 2026-11-11 | 71.5k | Active | Study (shadow git checkpoints) |
| openai/codex | Apache-2.0 | 2026-11-11 | 134.9k | Active | Not read this session |
| google-gemini/gemini-cli | Apache-2.0 | 2026-11-11 | 108.8k | Active | Not read this session |
| anomalyco/opencode (was sst/opencode) | MIT | 2026-11-11 | 226.1k | Active | Not read this session |
| OpenHands/OpenHands | MIT | 2026-11-11 | 93.2k | Active | Not read this session |
| Aider-AI/aider | Apache-2.0 | 2026-05-22 | 50.1k | Quiet since May | Reference (one git commit per edit) [memory] |
| anthropics/claude-code | No licence reported by the API | 2026-11-11 | 155.3k | Active | Docs only (checkpointing page fetched) |
| arsenetar/send2trash | BSD-3-Clause | 2026-06-16 | 0.3k | Maintained | Reference for trash-instead-of-delete |
| opentofu/opentofu | MPL-2.0 (weak copyleft, file level) | 2026-11-11 | 30.8k | Active | Study plan-then-apply; do not copy files |
| dtm-labs/dtm | BSD-3-Clause | 2026-01-03 | 10.9k | Quiet | Reference for saga |
| restic/restic | BSD-2-Clause | 2026-11-06 | 37.2k | Active | Optional (content-addressed snapshots) |
| kopia/kopia | Apache-2.0 | 2026-11-10 | 14.6k | Active | Optional |
| openSUSE/snapper | **GPL-2.0** | 2026-11-11 | 1.2k | Active | Docs only (pre/post snapshot pairs) |
| **Policy** | | | | | |
| authzed/spicedb | Apache-2.0 | 2026-11-11 | 7.2k | Active | Study the model |
| apache/casbin (was casbin/casbin) | Apache-2.0 | 2026-11-04 | 20.5k | Active | Study |
| apache/casbin-pycasbin | Apache-2.0 | 2026-11-07 | 1.8k | Active | The only pure-Python engine in this list |
| cerbos/cerbos | Apache-2.0 | 2026-11-11 | 4.7k | Active | Optional |
| ory/keto | Apache-2.0 | 2026-09-04 | 5.4k | Not archived | Optional |
| osohq/oso | Apache-2.0 | 2026-10-22 | 3.5k | **Archived** | Skip |
| cedar-policy/cedar-for-agents | Apache-2.0 | 2026-11-11 | 59 | Active, small | Study (derives a Cedar schema from MCP tool descriptions) |
| microsoft/agent-governance-toolkit | MIT | 2026-11-10 | 6.6k | Active, "public preview" | Study the interception model |
| responsibleai/agent-hooks | MIT | 2026-11-10 | 25 | New | Study (eight interception points; README only seen via the toolkit) |
| responsibleai/agent-control-spec | MIT | 2026-11-06 | 8 | New | Optional |
| agentgateway/agentgateway | Apache-2.0 | 2026-11-11 | 6.1k | Active | Optional (MCP and A2A proxy with policy) |
| IBM/mcp-context-forge | Apache-2.0 | 2026-11-11 | 4.8k | Active | Optional |
| docker/mcp-gateway | MIT | 2026-10-26 | 1.6k | Active | Optional |
| microsoft/mcp-gateway | MIT | 2026-11-04 | 0.9k | Active | Optional |
| strongdm/leash | Apache-2.0 | 2026-04-06 | 0.6k | Quiet | Optional (Cedar policies around agent processes) |
| eqtylab/cupcake | Apache-2.0 | 2026-03-02 | 0.3k | Quiet | Optional (OPA policies on coding-agent hooks) |
| invariantlabs-ai/invariant | Apache-2.0 | 2026-01-12 | 0.5k | Quiet | Optional (trace-level rules) |
| openai/openai-guardrails-python | MIT | 2026-11-10 | 0.3k | Active | Optional |
| guardrails-ai/guardrails | Apache-2.0 | 2026-11-11 | 7.6k | Active | Optional |
| eclipse-biscuit/biscuit (was biscuit-auth/biscuit) | Apache-2.0 | 2025-10-21 | 1.2k | Spec repo, quiet | Study (attenuable capability tokens) |
| superfly/macaroon | Apache-2.0 | 2026-11-06 | 0.1k | Active | Optional |
| ucan-wg/spec | NOASSERTION (file not read) | 2026-10-22 | 0.3k | Active | Optional |
| **Connectors** | | | | | |
| modelcontextprotocol/modelcontextprotocol | LICENSE: **in transition from MIT to Apache-2.0**; new contributions Apache-2.0 | 2026-11-11 | 9.7k | Active | Use as the public standard |
| modelcontextprotocol/servers | Same transition notice | 2026-11-11 | 91.9k | Active | Reference servers |
| modelcontextprotocol/registry | NOASSERTION (same family; file not read) | 2026-11-11 | 7.5k | Active | Reference |
| PrefectHQ/fastmcp | Apache-2.0 | 2026-11-11 | 28.4k | Active | Optional Python MCP library |
| sooperset/mcp-atlassian | MIT | 2026-11-10 | 6.1k | Active | Study (Jira and Confluence, Cloud and Server) |
| atlassian/atlassian-mcp-server | Apache-2.0 | 2026-11-07 | 1.2k | Active | Study (vendor's own) |
| github/github-mcp-server | MIT | 2026-11-11 | 34.4k | Active | Reference |
| taylorwilsdon/google_workspace_mcp | MIT | 2026-11-11 | 3.5k | Active | Study (calendar, mail, drive) |
| ComposioHQ/composio | MIT | 2026-11-11 | 31.0k | Active | Optional (SDK is MIT; the hosted service is not open) [memory for the second half] |
| airbytehq/airbyte-python-cdk | MIT | 2026-11-11 | 27 | Active | Study the declarative connector spec |
| meltano/sdk | Apache-2.0 | 2026-11-09 | 0.1k | Active | Optional (Singer taps) |
| kestra-io/kestra | Apache-2.0 | 2026-11-11 | 30.2k | Active | Optional |
| google/adk-python | Apache-2.0 | 2026-11-11 | 22.2k | Active | Optional |
| airbytehq/airbyte | **Elastic License 2.0** | 2026-11-11 | 22.4k | Active | Avoid code (the CDK repo above is MIT) |
| NangoHQ/nango | **Elastic License 2.0** | 2026-11-11 | 13.2k | Active | Avoid code |
| n8n-io/n8n | **Sustainable Use License** plus enterprise licence for `.ee` files | 2026-11-11 | 210.2k | Active | Avoid code |
| windmill-labs/windmill | **AGPLv3** mostly, some Apache-2.0, some proprietary | 2026-11-11 | 18.5k | Active | Avoid code |
| PipedreamHQ/pipedream | **Pipedream Source Available License 1.0** | 2026-11-11 | 11.8k | Active | Avoid code |
| frappe/hrms | **GPL-3.0** | 2026-11-11 | 9.0k | Active | Docs only (an HR system we may need to connect to, not copy) |
| **Injection research** | | | | | |
| ethz-spylab/agentdojo | MIT | 2026-06-02 | 1.0k | Quiet | Use as a test-suite idea |
| ServiceNow/DoomArena | Apache-2.0 | 2025-09-12 | 65 | Stale | Optional |
| facebookresearch/wasp | **CC-BY-NC 4.0**; **archived** | 2026-04-13 | 98 | Archived | Paper only |
| facebookresearch/Meta_SecAlign | **CC-BY-NC 4.0** | 2026-06-11 | 75 | Quiet | Paper only |
| microsoft/BIPIA | NOASSERTION (not read); **archived** | 2024-04-15 | 0.2k | Archived | Paper only |

Not found at the path tried: `mozilla/any-agent`, `google/android-mcp` (guesses, discard).

---

## 2. Findings by sub-area

### 2a. Browser control

**How the best projects work**

Three designs are in use, and the field moved between them during 2026.

*Accessibility snapshot with element references.* playwright-mcp, agent-browser, chrome-devtools-mcp and the Stagehand snapshot layer all do the same thing. The page is read through the browser's accessibility tree, pruned to interactive and labelled nodes, and printed as an indented text outline where each actionable node carries a short reference. The model answers with "click reference e7", never with coordinates or CSS. The tool resolves the reference to a backend DOM node, scrolls it into view, computes a clickable point, and dispatches real input events. agent-browser's README states two rules worth copying: references are valid only for the snapshot that issued them, and a click fails (it does not report success) when the target is hidden, disabled, off-screen or covered by another element such as a consent banner [README read]. Stagehand's capture step builds a hybrid of the DOM and the accessibility tree per frame, stitches iframes together by prefixing each child frame with the path of its host iframe element, and has a fast path that snapshots only the subtree of a known locator [read `packages/extension/understudy/a11y/snapshot/capture.ts` comments]. Stagehand also splits the work into `observe` (find candidate actions and return them as data) and `act` (execute one), so a caller can inspect or store the action before it runs [read docs v4].

*Code as action.* browser-use 1.0 dropped its indexed-DOM, one-action-per-step loop. The model now writes a Python cell per turn in a persistent REPL that has synchronous helpers over raw CDP; "one step is one model request (one Python cell)" [read `MIGRATING.md`, `agent/prompt.py`, `ax.py`]. Its fast mode still prints page state as a numbered list of accessibility nodes and offers click and type by node id. Good details in that code:
- Waiting is event based, never a fixed sleep: the page counts as settled when the document has parsed, there are no fresh in-flight requests (requests older than about 1.5 s are treated as long-poll or analytics), and the DOM has been quiet for about 80 ms, all bounded by a cap.
- Every action is bracketed by a cheap probe taken before and after, and returns one line saying "navigated to URL", "page changed" or "no change". That is a free, deterministic post-condition.
- Before clicking it checks that the point is not covered; if a fixed header covers it, it re-centres and retries, otherwise it raises a precise reason.
- JavaScript alert and confirm dialogs block all CDP calls, so a background watcher accepts them and reports their text.
- Secrets are typed by name through a dedicated helper and are masked in every output; domain-scoped secrets type only on their domain.
- Domain allow and block lists are enforced in three places (helper refusal, failing main-frame requests, and a sweep after each cell), and the file says plainly that this is "a guard for an aligned model, not a sandbox".
- The prompt tells the model that a failed call may have partly executed and must be inspected, never replayed automatically. That is the same rule `flow.py` already enforces in code for non-idempotent tools.

*Vision.* Screenshot in, coordinates out (the claude-quickstarts demo [memory], Magnitude, Midscene, the hosted computer-use models). Used when the page is canvas, a remote desktop, or has a broken accessibility tree.

**Measured results (as fetched; treat cross-row comparison with care)**

- WebVoyager, third-party board (steel.dev, fetched): 99.19% for an open harness on a closed frontier model (self-reported, 2026-06); Alumnium 98.5% (2026-03); Magnitude 93.9% (2025-07); browser-use 89.1% (its own report, 2024-12, 586 tasks). The board itself warns that WebVoyager scores depend on task drift, removed tasks and the choice of judge. It is close to saturated and is no longer a useful discriminator.
- WebArena, same board (fetched, all self-reported): 74.3% top (2026-02), then 71.6%, 71.2%, 68.0%.
- Cost per task: no comparable public figure was fetched for the browser frameworks. Stagehand's answer to cost is caching; browser-use's is a cheaper default model. OpenAdapt publishes about USD 0.08 and 36.5 s for one form entry by a frontier computer-use model against USD 0 and 3.3 to 22.5 s for its compiled program (its own benchmark, see 2c).

**What they get wrong**

- browser-use 1.0 gives the model a general Python interpreter with subprocess access. One "action" is an arbitrary program, so it cannot be classified as reversible or not before it runs, cannot be approved meaningfully, and cannot be replayed step by step. That is the opposite of "models propose, code decides". Its defaults also route through a paid cloud browser and model gateway.
- Stagehand's cache now lives on the vendor's servers and has no effect with a local browser.
- All of them treat page text as trusted enough to show the planner. None binds an approval to the page state that was seen.
- None classifies actions by consequence. A click on "Delete account" and a click on "Next page" are the same tool call.
- Success is judged by the model or by a screen diff; none of the browser frameworks reads the system of record back.

**Minimum original design for us (about 450 lines of Python on Playwright's CDP session, or about 600 on a raw CDP websocket)**

A browser interface is a small, fixed set of tools registered with the existing `Flow`:

- `browser.snapshot()` returns a compact outline of interactive and labelled nodes with references, plus a `snapshot_id` (hash of URL, document id and outline). Read only, idempotent, no approval.
- `browser.read(ref)` returns the text of one subtree. Read only.
- `browser.open(url)`, `browser.click(snapshot_id, ref)`, `browser.fill(snapshot_id, ref, text)`, `browser.select(...)`, `browser.press(key)`, `browser.upload(snapshot_id, ref, path)`, `browser.back()`.
- Every acting tool takes the `snapshot_id` it was planned against. If the live page no longer matches, the tool fails closed and the model must snapshot again. Because `flow.py` hashes tool plus arguments, an approval is then bound to the exact screen the approver was shown. This is the single most useful addition.
- Every acting tool returns the before/after verdict line (navigated / changed / no change) and fails rather than succeeds on covered, hidden or disabled targets.
- The full snapshot is stored by content hash outside the event row; the row keeps the hash. `MAX_OUTPUT_CHARS` is 4,000, so the model sees only the pruned outline.
- A click is not one risk class. The verdict comes from a deterministic classifier over the target: role, accessible name, form method and action URL, input type (password, payment, file), and destination origin. "Submit", "send", "pay", "delete", "confirm", "publish", any cross-origin form post, and any file upload go to approval. Everything unclassified goes to approval (fail closed), and the allow-list grows from the ledger.
- Navigation is limited by an origin allow-list per run.

**What would go beyond them**

- Observation-bound approvals (above); nobody in the browser group does this.
- Read-back verification for writes: after a submit, confirm through the application's API or a fresh page load that the record exists exactly once (see OpenAdapt in 2c).
- Per-origin memory of which controls proved consequential, learned from the ledger.

### 2b. Desktop control

**How the best projects work**

*Accessibility-tree first.* agent-desktop (new in 2026, Apache-2.0) reads the OS accessibility tree on macOS, Windows and Linux and returns JSON with a reference for every actionable element; references are namespaced by `snapshot_id`, a bare reference is rejected, and a changed UI returns `STALE_REF` or `AMBIGUOUS_TARGET` [README read]. It has no model inside; the loop belongs to the caller. computer-use-linux (MIT) does the same for Linux through AT-SPI, with compositor-aware window targeting, Wayland input through uinput or the remote-desktop portal, semantic selectors (role, name, text, states) preferred over pixels, direct `set_value` and `perform_action` on elements, a post-action screenshot plus tree in the same round trip, and a single machine-readable readiness report [README read]. cua's driver (MIT part) drives macOS apps in the background without taking focus or moving the user's pointer, and adds one rule worth copying: a click derived from a parsed screenshot region must carry the same one-use `capture_id` as the observation it came from [read `libs/cua-driver/README.md`]. UFO (MIT, Windows) combines UIA, Win32 and COM, prefers a native API call over a click when one exists, and batches several predicted steps into one model call that is validated against the live UIA state, which its README says removes up to 51% of model queries [README read]. It also has an explicit confirmation state before dispatching an action [test file header read].

*Screenshot plus grounding model.* Agent S3 (Apache-2.0) [read `gui_agents/s3/agents/worker.py`, `grounding.py`, `bbon/behavior_narrator.py` outlines]:
1. A worker model sees the screenshot and the task and emits one action from a small action interface whose targets are natural-language descriptions ("the Save button in the toolbar"), not coordinates.
2. A separate grounding model turns each description into a point; coordinates are rescaled from the grounding model's resolution to the screen's. For text spans, OCR produces word boxes and a model picks the first and last word.
3. A reflection model reviews each step against the trajectory and feeds a short note into the next turn.
4. A code agent handles sub-tasks that are better done by a script (for example setting spreadsheet cells directly).
5. History is trimmed to the last eight screenshots with all text kept.
6. "Behaviour best-of-N": run several complete attempts, describe each step as a before/after fact using annotated and zoomed crops, and have a judge pick the best attempt.

*Screen parsing.* OmniParser detects icons and text regions and labels them so that any model can pick a numbered box. Useful for pixel-only surfaces; licence care is needed (table above).

**Measured results (as fetched)**

- Agent S3 README: 66% on OSWorld alone at 100 steps, 72.6% with best-of-N; WindowsAgentArena 50.2% to 56.6% with three attempts; AndroidWorld 68.1% to 71.6%.
- Official OSWorld-Verified page (fetched): the top entries are now general frontier models at 80 to 86% (100 steps), a specialised open-weight model at 80.4%, and older open agents in the 40 to 57% range. Third-party pages give slightly different leaders (one lists an open-weights model at 86.1%, self-reported, with a note that the evaluated vision checkpoint may not be the released one; another cites a 90.19% entry that I could not confirm on the official page).
- OSWorld V2 (strict pass/fail): Agent S4 README reports 21.3% with an open 27B model, above two named frontier models at 13.0% and 20.6%, at about 4.3% and 1.5% of their cost. Later vendor-reported V2 figures up to about 49% binary appear on a third-party page only [unverified].
- The honest reading: on realistic multi-step desktop work, more than half of strict tasks still fail, and the headline gains came from running several attempts and choosing one. Best-of-N is only usable where attempts are free of side effects, which is a sandbox, not someone's real desktop.

**What they get wrong**

- Best-of-N assumes actions cost nothing. On a real machine three attempts means three sent messages.
- Agent S3 executes model-written automation code on the host; its README says to "use with care".
- Pixel coordinates carry no meaning, so nothing downstream can decide whether an action is safe.
- Screenshots bypass text-based injection scanning entirely.
- Accessibility trees are incomplete for canvas apps, games, some Electron and Java apps, and remote desktops.
- On macOS the agent process needs the Accessibility and Screen Recording grants, which are all-or-nothing for the whole user session.

**Minimum original design for us (macOS first; about 350 lines over the AX API through PyObjC, plus about 150 for screenshots and input events)**

Same shape as the browser interface, so the model learns one pattern:

- `desktop.apps()`, `desktop.windows()`, `desktop.snapshot(app, window)` return a pruned AX outline with snapshot-scoped references. Read only.
- `desktop.press(snapshot_id, ref)` performs the element's own AX action; `desktop.set_value(snapshot_id, ref, text)` writes the value directly; `desktop.menu(app, path)` picks a menu item by its path. These three cover most work without synthetic mouse events and without stealing focus.
- `desktop.key(app, chord)` and `desktop.click_at(capture_id, x, y)` are the fallbacks. `click_at` is always approval-required unless the run is inside a sandbox, because code cannot know what is under the point.
- PyObjC is a new dependency. The alternative with no dependency is JavaScript for Automation through `osascript`, which is slower and clumsier but ships with the OS. Decide when building; either fits behind the same tools.
- Linux later through AT-SPI and Windows through UIA behind the same tool names. Do not build these until macOS works.
- For anything risky or unknown, run the desktop interface inside a disposable VM (Lima is Apache-2.0; the Lume part of cua is MIT; both use Apple's Virtualization framework on Apple Silicon). Inside a VM, a snapshot before the run makes every local action undoable, and best-of-N becomes legitimate.
- Skip a grounding model for now. Add one only when a target app has no usable tree.

**What would go beyond them**

- One reference discipline (snapshot-scoped, stale means fail) across browser and desktop, tied into the approval hash.
- Prefer API over GUI as policy, not as an optimisation: if a connector exists for the target system, the planner is not offered the GUI tool for it.
- Consequence classes on elements (2d), which none of the desktop agents have.

### 2c. Record and replay

**How the best projects work**

OpenAdapt (MIT) is the strongest thing found in the whole slice [read README, `packages/flow/DESIGN.md`, `docs/GUARDED_SAVE.md`, `docs/AFTER_A_STOP.md`]. Its present design:

- *Record.* One demonstration by a person or an agent produces an ordered event list (click, type, key, scroll, with coordinates and timing), a before and after frame per event, and metadata. A typed value is marked as a parameter at record time.
- *Compile.* The recording becomes a workflow: a flat list of steps, each with an anchor (how to find the target again) and post-conditions (how to know it worked). The anchor holds a structural locator when the backend has structure (DOM selector or role plus name; UIA automation id or role plus name) and an image crop as fallback. Later versions lift the flat list into a parameterised state machine with loops and guards, induced from one or more traces, and "quarantine" a workflow when intent remains ambiguous.
- *Replay.* No model calls. Each step is resolved through a "resolution ladder": structural locator first, visual match as the floor for pixel-only surfaces. Post-conditions are checked after each step. Scroll steps carry no post-condition; they are verified by the next step finding its target.
- *Heal.* When the UI has drifted, the run stops before saving. An agent proposes a fix as a reviewable diff, the program tries it up to the save without saving, and a person approves it.
- *Guarded save.* Around any write: before, confirm the open record is the one the task names and read the system of record; at the write, hold for approval if the mode requires it and commit once only; after, read the system of record again through its API or database, not the screen. Verdicts are VERIFIED, REFUTED (do not retry; a person corrects) or RECONCILIATION_REQUIRED.
- *After a stop.* "A stop isn't a rollback." Each run report has a change ledger listing every step that could have changed the application; a declared undo step runs only after a person approves; undo steps can be proposed per saving step and tried on a test copy first; programs that write before a check they could have done first are flagged.

Its own measurements: on a test copy of an open-source medical records system, a frontier computer-use agent took a median 36.5 s and about USD 0.08 per entry with 62 of 63 saved correctly; the compiled program took 22.5 s through the screen or 3.3 s through one API call, at no model cost, 18 of 18. With faults injected into the database, the agent claimed success on all 30 bad saves; the read-back caught 25 of 30. In a separate test of 72 bad saves, the on-screen "Saved" message reported 54 as saved, a REST read reported 9, and a read of every table reported 0. These are the project's own numbers on its own harness.

Other reference points: Playwright's recorder and trace viewer (actions with before/after DOM snapshots, network and console; selectors chosen by role and accessible name first) [memory]; the Chrome DevTools Recorder format in puppeteer/replay (JSON steps, each with several alternative selectors) [README not re-read, memory]; rrweb (records DOM mutations for pixel-faithful replay of what was seen, not for re-execution) [memory]. Stagehand's `observe` returns an action as data that can be stored and replayed without a model [docs read]. Classic RPA tools (TagUI, rpaframework) are hand-written scripts.

**What they get wrong**

- Pure coordinate replay breaks on the first layout change; pure selector replay breaks on redesigns. Only the ladder approach survives both.
- Most recorders capture what was done, not why; parameters and branches have to be guessed. OpenAdapt's quarantine is the honest answer.
- Recordings capture secrets and personal data on screen.

**Minimum original design for us (about 400 lines)**

A recording is nothing new: it is a `flow.py` run. A run's events already hold every tool call with arguments and results, in order, hash-chained. So:

- *Record* a person's demonstration by writing the same `call` and `result` events from an observer (browser: CDP input and navigation events mapped to the nearest snapshot reference; desktop: AX notifications), with actor set to the person.
- *Compile* = take a finished run, replace literal argument values that came from the task with named parameters, replace each reference with an anchor (role, accessible name, ancestor path, and neighbouring label text), and keep each step's observed post-condition. The output is a JSON procedure: steps of tool name, argument template, anchor, expected post-condition, effect class.
- *Replay* = feed the steps to the same `Flow` with a scripted proposer in place of the model. Every step still passes through `permit`, approval and the ledger, so a replayed procedure has exactly the authority of the person running it.
- *Drift* = an anchor that does not resolve uniquely stops the run before any write; the model may propose a repaired anchor, which is shown as a diff and needs approval.
- Redact with `guard.redact` before storing any recording.

**What would go beyond them**

- Procedures are ledger-native, so "who taught this, who approved it, which runs used which version" is provable.
- Promotion ladder: a procedure that has replayed N times with verified post-conditions can be offered a lower approval requirement for its undoable steps only.

### 2d. Reversibility

**How real systems do it**

*Snapshots of the filesystem.* Copy-on-write filesystems (APFS, btrfs, ZFS) take a snapshot of a volume or subvolume in constant time; a rollback discards everything after it. An overlay filesystem gives the same effect per process: writes land in an upper directory that can be thrown away or merged. snapper pairs a "pre" and a "post" snapshot around each system change so the pair is the undo unit [docs, memory]. Limits: on macOS, creating a local APFS snapshot is easy but reverting a live volume to one is not something an unprivileged process can do [memory; verify before design]; what does work for a user process is per-file copy-on-write clones, which make a pre-image copy of a file nearly free. Snapshots cover local files only.

*Per-action undo log.* Before a change, store the pre-image or the inverse operation; undo applies the entries in reverse. jj keeps an operation log for the whole repository and can undo any operation, including ones that rewrote history [memory]. Editors and databases (write-ahead and undo logs) work the same way.

*Trash instead of delete.* A delete becomes a move to a holding area with the original path recorded; undo is a move back. send2trash does this through each OS's own trash [not read].

*Version-control-backed workspace.* Coding agents use a shadow git repository. Cline's docs: a separate repository, a commit after every tool use, it captures untracked files too, the user's own history is untouched, and each checkpoint can be compared or restored; the stated cost is storage and slowness on very large repositories [read `docs/core-workflows/checkpoints.mdx`]. Claude Code's docs: a checkpoint before each user prompt; code and conversation can be restored separately; changes made only by shell commands are not tracked, edits by sub-agents are usually not captured, symlinked paths are skipped, and nothing outside the working files is covered [docs fetched]. container-use gives each agent its own container and git branch [README not read]. The shared lesson is that these features undo file edits and nothing else.

*Saga and compensating actions.* A multi-step change across systems that cannot share a transaction is a sequence of steps, each registered with a compensating step. On failure the compensations run in reverse order. A compensation is a new forward action (cancel the booking, delete the created ticket, post a reversing entry), not a rewind: it can itself fail, and the intermediate state was visible to others. Temporal's workflow model is the usual host for this [covered in the earlier brief; not re-read].

*Dry run and plan-then-apply.* Compute the full set of changes as data, show it, apply only that exact plan. Terraform and OpenTofu save the plan and refuse to apply it if the state has moved since [memory]. This does not undo anything; it moves the decision before the effect.

*Transactional outbox and delayed send.* The intent to send is written in the same database transaction as the business change; a separate dispatcher sends it later. If the dispatcher waits a grace period, "undo" is deleting the row before it leaves. This is how "undo send" in mail clients works: the message has not gone.

*Soft delete, versioning and tombstones* in the target system (document history in wikis, issue history in trackers, a recycle bin) are the remote equivalent of trash.

**What cannot be reversed, and the standard mitigation**

A message that has been delivered, a payment that has settled, a post that others have read, a webhook that another system has acted on, a credential or personal data item that has been disclosed, a physical action, and the passage of a deadline cannot be undone by any mechanism. Compensations exist for some (a refund, a correction notice, a deletion request, rotating the leaked credential) but the original effect was observed. The mitigations are all "before", not "after":

1. Hold it: outbox with a grace period, during which it is still undoable.
2. Show it: plan-then-apply with the exact payload, recipient and amount in the approval.
3. Bound it: amount ceilings, recipient allow-lists, rate limits, one-shot approvals bound to the exact arguments.
4. Split it: two-person approval above a threshold.
5. Make it idempotent: a key derived from the call so a retry cannot double-send.
6. Verify it: read the system of record back and reconcile; never trust the success screen.

**Three-class model for us**

- **Undoable**: code holds everything needed to restore the prior state, restoring is local and deterministic, and no third party saw the intermediate state. Example: a file edit with a stored pre-image, a queued-but-unsent message.
- **Compensatable**: a new forward action can restore the business state, but it can fail, may need its own approval, and the original was visible. Example: a created ticket, a calendar event without attendees, an approved leave request.
- **Irreversible, needs approval**: no action restores the world. Example: a sent mail, a payment, a public post, a deleted remote record with no recycle bin. Also the default class for anything unclassified.

### 2e. Policy and permission engines

**How they work**

- *Cedar* (Apache-2.0, Rust): each request is principal, action, resource and context; policies are `permit` or `forbid` statements with conditions; the default is deny and any matching forbid overrides every permit; policies are validated against a schema and can be analysed formally [memory for semantics]. cedar-for-agents generates a Cedar schema and authorisation requests from an MCP server's tool descriptions, with Python and WebAssembly bindings [README read].
- *OPA* (Apache-2.0, Go): a general rule language (Rego) evaluated over JSON input and data; runs as a sidecar or library; produces decision logs; policies ship as bundles [memory].
- *OpenFGA and SpiceDB* (both Apache-2.0, Go; Zanzibar-style): store relationship tuples ("user U is manager of team T", "team T owns document D") and answer "does U have relation R to object O" by walking the graph, with a schema that defines how relations compose [memory]. They answer who-is-related-to-what, not is-this-amount-under-the-limit.
- *Casbin* (Apache-2.0; now under the Apache organisation): a model file defines the request shape, policy shape, matcher and effect; one engine covers ACL, RBAC and ABAC. pycasbin is the only pure-Python engine in this group [README not read].
- *Agent-specific*: Microsoft's agent-governance-toolkit intercepts every tool call, message and delegation in deterministic code before execution, with tamper-evident decision records; its policy engine is published separately as a spec with a hooks contract of eight interception points [README read]. Its stance is the same as ours: "prompt-level safety is not a control surface". Smaller projects wrap coding agents with Cedar (leash) or OPA (cupcake) rules. MCP gateways (agentgateway, context-forge, the Docker and Microsoft gateways) put policy at a proxy in front of tool servers.
- *MCP authorisation* (draft spec, latest dated 2026-07-28, fetched): OAuth 2.1; the MCP server is a resource server and must publish protected-resource metadata (RFC 9728); clients must send a resource indicator (RFC 8707) and servers must check the token audience; PKCE is required; servers must not accept or pass through tokens issued for anything else; scopes are requested by challenge with least privilege and stepped up on `insufficient_scope`; client identity is by client-ID metadata document or pre-registration, with dynamic registration kept only for compatibility. This governs which client may reach which server. It says nothing about whether a particular call is wise.
- *MCP tool annotations* (read-only, destructive, idempotent, open-world hints) exist, and the spec treats them as untrusted hints from the server [memory]. activepieces exposes the same idea: each action can declare `idempotent` in metadata for agents, and its docs say the flag informs retry safety but does not enforce anything [docs read].
- *Capability designs*: instead of asking a central engine, the caller holds an unforgeable token that names exactly what it may do, and can only narrow it when passing it on. Macaroons and Biscuit tokens add offline attenuation (append a caveat such as "only this recipient, only until 17:00") [memory]. The CaMeL design in the earlier brief is the data-flow version of this.

**What they get wrong for our purpose**

- None has a notion of reversibility or of approval as a third outcome. They return allow or deny; "allow if a named person approves this exact call" has to be built on top.
- All except pycasbin need a non-Python runtime or a sidecar.
- Server-declared safety hints are self-reported.

**Minimum original design for us (about 200 lines, no new engine)**

`authz.py` already has the Cedar shape: default refuse, a NEVER list that overrides every grant, typed actions, limits, and a pure function. Keep it. Add one thin function that becomes `Flow`'s `permit`:

1. Map the tool call to an action type and a resource (for example `browser.click` on a "Submit leave request" control at an allowed origin becomes `leave.submit` on that tenant).
2. Take the tool's declared effect class, then let the argument classifier raise it (never lower it).
3. Call `authorize`. NEVER and unknown action types deny.
4. Combine: irreversible always needs approval whatever the autonomy level, until a narrow standing grant exists; compensatable needs approval unless autonomy is "act then notify" or higher and a compensation is registered; undoable is allowed at "act with approval" and above once the undo data is captured; reads are allowed inside the origin and path allow-lists.
5. Any exception or unmapped call returns "approve", which `flow.py` already does.

Replace the always-allow path in `core/policy/engine.py` with a call to this function rather than growing a second rule system. Relationship questions (who manages whom, who owns which record) are a Postgres table of tuples and one recursive query; adopt a Zanzibar engine only if that query becomes the bottleneck. Adopt the Cedar policy format only if customers need to write their own rules.

**What would go beyond them**

- Effect class as a first-class input to the decision.
- Approvals as scoped, expiring, attenuated grants recorded in the ledger (a capability: this tool, these argument bounds, this run, until this time), instead of sticky "always allow".
- The session trust bits from the earlier brief (has read untrusted content, has sensitive access, can act externally) as context to the same function.

### 2f. Connectors

**How open frameworks define an integration**

*activepieces* (MIT outside the enterprise directories) [read framework trigger file outline, polling helper outline, docs for auth, triggers and AI metadata]:
- A "piece" is a package with one auth definition, a list of actions and a list of triggers.
- Auth kinds: secret text, basic, custom (a form of fields with a validate callback and an optional server-side token refresh), and OAuth2 with a declared grant type and scopes.
- An action has a name, typed input properties (with dynamic dropdowns that call the API), and a run function receiving auth, inputs, a key-value store and file helpers. Optional agent metadata: a longer description and an `idempotent` flag; an `audience` field controls whether humans, agents or both see it.
- A trigger has a strategy (polling, webhook, or app webhook), `onEnable` and `onDisable` hooks (register and remove the webhook), a `run` that returns a list of events, sample data, an optional handshake configuration and an optional renewal schedule for expiring webhooks.
- Polling is a shared helper with two de-duplication strategies: time based (store the newest timestamp seen, emit only newer items) and last item (store the last id seen). There is a cap on items per poll.
- Pagination and rate limits are not part of the declared shape; each action handles them in code.
- The Jira Cloud piece now ships a parallel set of agent-oriented actions next to the human ones.

*Airbyte's Python CDK* (MIT, separate repo from the ELv2 platform) [not read this session; memory]: a connector is declared as data: streams, a requester (base URL, path, auth), a paginator (cursor, offset or page), a record selector, an incremental cursor field, and an error handler with back-off rules keyed on status codes and rate-limit headers. It is read-oriented (extract) and has little to say about write actions.

*Model Context Protocol*: a connector is a server exposing tools (name, description, JSON schema for input, optional annotations), resources and prompts over stdio or HTTP; authorisation as in 2e. Verified servers relevant to us: sooperset/mcp-atlassian (MIT; Jira and Confluence), atlassian/atlassian-mcp-server (Apache-2.0; the vendor's own), taylorwilsdon/google_workspace_mcp (MIT; calendar, mail, drive), github/github-mcp-server (MIT). No widely used open MCP server for the common HR suites was found in this pass [unverified gap; search was not exhaustive].

*Avoid as code sources*: n8n (Sustainable Use), Nango and Airbyte platform (ELv2), Pipedream (source-available), Windmill (AGPL). Their public docs can be read for API quirks.

**What they get wrong**

- None declares consequence. "Create issue", "delete issue" and "transition issue to Done" differ only by name.
- None pairs an action with its inverse.
- Idempotency is a hint at best.
- Pagination and rate limiting are per-connector code, so behaviour under throttling varies.
- An MCP server's descriptions and results are untrusted third-party text that goes straight to the model.

**Minimum original design for us (about 300 lines for the spec and runner, about 250 for a minimal MCP client)**

One Python dict per connector, loaded at start:

- `auth`: kind (api key, basic, OAuth2 authorisation code with PKCE), scopes requested, where the token lives. Tokens never enter a prompt or an event row.
- `actions`: each with name, input schema, HTTP method and path template, `effect` class, `idempotency` (how the key is derived and where it is sent), `inverse` (the action and argument mapping that compensates it, or none), `verify` (the read that confirms the write), and a human-readable preview template for approvals.
- `reads`: each with a paginator kind (cursor, offset, link header) and a cap.
- `triggers`: polling with a stored cursor, or webhook with register, unregister, signature check and renewal.
- `limits`: one shared limiter per connector honouring `Retry-After`, with capped exponential back-off; retries only for actions marked idempotent.

Each action becomes a `flow.Tool` with the flags filled from the spec. An MCP server is wrapped the same way: its tools default to irreversible-needs-approval until we classify them in a local overlay file; its annotations may raise a class but never lower it; its descriptions and outputs pass through `guard.scan` and `guard.wrap`. Start with Jira and one calendar, because both have clean inverses (delete or transition back; cancel event) and an activity history to verify against.

**What would go beyond them**

- Inverse and verify as required fields for every write.
- The same connector spec drives the API tool and tells the planner not to use the GUI for that system.

### 2g. Prompt injection against computer-use agents

**What is specific to this setting**

The agent reads content written by strangers (pages, mail, documents, calendar invites, file names, issue comments, tool descriptions) and can then act with the user's logged-in sessions. Injection can be visual: text in an image, a fake dialog, a pop-up, an overlay that looks like the application's own interface; none of that passes through a text scanner. One click can be the whole attack.

**Published evidence (fetched)**

- VPI-Bench (ICLR 2026 poster): 306 cases on five platforms; computer-use agents were deceived at rates up to 51% and browser-use agents up to 100% on some platforms; existing defences gave limited protection.
- Anthropic's browser-extension report: against an internal adaptive attacker, attack success with the model alone was 8.0% to 13.8% across four models, and 1.4% to 2.4% with improved safeguards. The post states that about 1% "still represents meaningful risk" and that no browser agent is immune. Defences named: classifiers over all untrusted content entering the context, including hidden text and manipulated images.
- A 2026 replication on the AgentDojo suite (journal article, snippet only): with spotlighting, attack success was roughly 56% to 78% depending on model; with a prompt-injection detector, about 30%. Spotlighting is the technique `guard.wrap` implements, so on its own it is weak.
- Secondary reports (not read at source): a system card giving 4.7% success at one attempt rising to 63% at 100 attempts in a coding environment; crawl telemetry showing a 32% relative rise in pages carrying injection text between November 2025 and February 2026; a browser vendor's design using a separate critic model that sees only action metadata, never page content, together with a per-task set of origins the agent may read or act on.
- Earlier brief already covers CaMeL, the Rule of Two and classifier layers; not repeated here.

**Defences that hold up, in order of strength**

1. *Structural*: the model that has read untrusted content cannot authorise anything. `flow.py` already has this. It bounds the damage; it does not stop the injection landing.
2. *Capability bounds per task*: an origin allow-list for reading and a tighter one for acting; no cross-origin form posts or uploads without approval; secrets typed by name through a helper and scoped to a domain.
3. *Break the trifecta*: a run that has read untrusted content and holds sensitive access needs approval for any outward-going action.
4. *A critic that never sees the content*: deterministic checks first (does this action's target and destination fit the task's declared scope), then optionally a second model that sees only the task and the proposed call.
5. *Human approval bound to the exact action and the exact screen* (snapshot id in the hashed arguments).
6. *Detection* (pattern and classifier scans): cheap, catches the lazy cases, and useful as a signal for raising the approval requirement. Never the only layer.
7. *Isolation*: a separate browser profile with only the sessions the task needs; a VM for unknown desktop work.

**What our current guard gets right and wrong**

- Right: tool output is scanned and wrapped before the model sees it, and a blocked output is withheld.
- Gap: screenshots are not text. Prefer DOM and accessibility text for observation; when a screenshot is needed, OCR it and scan the text, and never let a screenshot-only observation justify a consequential action without approval.
- Gap: hidden content. The snapshot should include only nodes that are rendered and visible to a person, and flag text that is present but hidden (zero size, off-screen, same colour as background) as a high-risk signal rather than passing it on.
- Gap: a regex scan will both miss attacks and block harmless pages that discuss prompt injection. Treat "block" on a browser observation as "withhold and require approval for the next acting step", and log it.
- Gap: the approval prompt itself can be attacked by showing the approver page-derived text. Build the approval preview from the tool arguments and the classifier's facts, not from model prose.

**Size**: about 150 lines on top of the existing guard (visibility filter, origin lists, session bits, preview builder).

---

## 3. How this plugs into the existing loop

Nothing in `flow.py` needs a redesign. Three additions:

1. **Three optional fields on `Tool`**: `effect` (read, undoable, compensatable, irreversible; default irreversible), `undo` (a callable that takes the stored undo data and restores the prior state, for undoable tools) and `inverse` (the name of the compensating tool and an argument mapping, for compensatable tools). `needs_approval` stays, but in practice `permit` (2e) decides.
2. **A wrapper around tool execution** that, between the existing `exec` and `result` events, captures the before-observation, captures undo data (pre-image, trash path, outbox row id, created record id), runs the tool, captures the after-observation and runs the post-condition. The undo data and observations go to a content-addressed blob store; their hashes go into the event.
3. **Two operations on `Flow`**: `undo(run_id, seq, by)` and `replay(run_id, params)`. Undo walks back from the end of the run to the chosen step; undoable steps are reversed directly; compensatable steps are proposed as new calls that go through `permit` and approval like any other; an irreversible step stops the walk and reports what remains. Each undo is itself appended as an event, so the chain shows both the action and its reversal.

Interfaces as tool sets:

| Interface | Tools | Idempotent | Default class | Notes |
|---|---|---|---|---|
| Browser | snapshot, read | yes | read | allowed inside the origin list |
| Browser | open, back, scroll, hover | yes (to a URL) | read | navigation outside the list is denied |
| Browser | click, fill, select, press, upload | no | set by the element classifier; unknown means irreversible | approval bound to snapshot id |
| Desktop | apps, windows, snapshot | yes | read | |
| Desktop | press, set_value, menu, key | no | set by the element classifier | |
| Desktop | click_at | no | irreversible outside a VM | |
| Files | read, list, stat | yes | read | path allow-list |
| Files | write, move, mkdir | write keyed by content is idempotent | undoable | pre-image stored first |
| Files | delete | yes | undoable | implemented as move to a run-scoped trash |
| Terminal | run (allow-listed read commands) | yes | read | |
| Terminal | run (anything else) | no | irreversible, unless run in a sandbox with a workspace snapshot, then undoable for files only | network off by default |
| Connector | each read | yes | read | |
| Connector | each write | from the spec | from the spec | inverse and verify required |
| Outbox | queue | yes (keyed) | undoable until the grace period ends | |
| Outbox | dispatch | yes (keyed) | irreversible | done by code after the grace period, never by the model |

**Ledger entry for one action.** `flow.py` already writes `call` (tool, args, verdict, call hash), `decision` (approve, by, note), `exec` and `result`. To make an action replayable and undoable, the set of events for one action should together hold:

- Identity: run id, sequence number, previous hash, own hash, timestamp (already there).
- Who and why: actor, on whose behalf, the task text hash, the procedure id and version if this is a replay.
- What: interface, tool, arguments (secrets by name only), call hash, idempotency key.
- Target: for UI actions, the snapshot id and the anchor (role, accessible name, ancestor path, origin or app and window); for connectors, the resource id.
- Decision: effect class as declared and as classified, the policy outcome and reason, the delegation id from `authorize`, the approver, the approval scope and expiry.
- Evidence: hash of the before-observation, hash of the after-observation, the post-condition and whether it held, a verification verdict (verified, refuted, needs reconciliation) with the source that was read.
- Reversal: the undo kind (pre-image, trash path, outbox row, inverse call), a pointer to the undo data, an undo-valid-until time if it expires, and after an undo, a link to the event that performed it.
- Trust: guard scan level for the observation, the session trust bits at the time of the call.
- Outcome: ok or not, error class, duration, model and token cost for the proposing turn.

Blobs (snapshots, screenshots, pre-images) are stored once by hash, redacted first, with their own retention period; the chain keeps only hashes, so deleting a blob for privacy does not break verification.

---

## 4. Reversibility table

| Action type | Class | Mechanism | What remains irreversible |
|---|---|---|---|
| Read a file, page or record | Read | None needed | Disclosure: once the model has read it, it may appear in later output |
| Create or edit a local file | Undoable | Store pre-image (copy-on-write clone where the filesystem supports it), or a shadow git commit of the workspace | Other programs that already read the new content |
| Delete a local file | Undoable | Move to a run-scoped trash with original path recorded | Nothing until the trash is purged; purging is irreversible |
| Move or rename a file | Undoable | Log the inverse move | Programs that reacted to the old path vanishing |
| Shell command inside a sandbox with a workspace snapshot | Undoable for files | Overlay or snapshot discard | Any network call it made |
| Shell command on the host | Irreversible, needs approval | Allow-list of read-only commands; everything else approved with the exact command line | Everything it did |
| Install or remove software, change system settings | Irreversible, needs approval (compensatable in some cases) | Record the previous setting; VM snapshot if in a VM | Side effects of install scripts |
| Type into a web form without submitting | Undoable | Reload or clear | Sites that save drafts or send keystrokes as you type |
| Submit a web form | Whatever the classifier says; unknown means irreversible | Read-back verification; inverse through API if the system has one | Notifications and downstream automation fired by the submit |
| Create a ticket, page or comment | Compensatable | Delete or archive by id; history remains | Notification mail already sent to watchers |
| Edit a ticket or wiki page | Compensatable | Restore the previous version from the system's history | People who read the interim version |
| Transition a workflow state (approve leave, close ticket) | Compensatable | Reverse transition where the workflow allows it | Downstream effects (payroll run, SLA timers, notifications) |
| Create a calendar event with no attendees | Compensatable | Delete it | Nothing significant |
| Create or change an event with attendees | Irreversible, needs approval | Cancel or correct, which sends another notice | Invitations already delivered |
| Queue a message in the outbox | Undoable until the grace period ends | Delete the outbox row | Nothing |
| Send mail or chat message | Irreversible, needs approval | Grace-period hold before dispatch; preview of exact recipients and body | Delivery. Recall features are unreliable; a correction is a second message |
| Post to a public or third-party site | Irreversible, needs approval | Hold and preview; delete after the fact where offered | Copies, caches, people who saw it |
| Payment or transfer | Irreversible, needs approval; ceiling in the NEVER rule | Idempotency key; two-person approval above a threshold; refund as a separate compensating payment | Settlement, fees, the counterparty's actions |
| Delete a remote record | Compensatable if the system has a recycle bin, otherwise irreversible | Prefer archive or soft delete; export before delete | Hard-deleted data |
| Change permissions or share a document | Compensatable | Revoke the grant | Whatever was copied while access existed |
| Upload a file to a third party | Irreversible, needs approval | Delete request afterwards | The third party's copies |
| Rotate, create or reveal a credential | Irreversible, needs approval | Rotate again | Exposure during the window |
| HR actions on the NEVER list (hire, terminate, pay change, sign contract) | Refused | `authz.py` NEVER list | Not applicable: the agent may only prepare a draft for a person |

---

## 5. Open questions and unverified items

**Not verified this session**

- Contents of anthropics/claude-quickstarts (computer-use demo), openai/codex, google-gemini/gemini-cli, opencode and OpenHands checkpoint or undo features: repos confirmed to exist with the licences listed, source and docs not read.
- Cedar, OPA, OpenFGA, SpiceDB, Casbin, Biscuit and macaroon semantics are stated from memory; only repo metadata and the cedar-for-agents README were fetched.
- MCP tool annotation names and their "untrusted hint" status: memory. The authorisation spec summary was fetched from the draft page (dated 2026-07-28); the latest *released* version was not checked separately.
- Airbyte CDK declarative model, Playwright codegen and trace details, puppeteer/replay format, rrweb, jj operation log, Terraform saved-plan behaviour, snapper pre/post pairs, send2trash behaviour: memory.
- APFS: whether an unprivileged process can create a local snapshot, and how files can be restored from one without a reboot, must be tested on the target macOS version before relying on it. Per-file clones are the safer assumption.
- Benchmark numbers conflict between sources. The official OSWorld page and two third-party trackers list different leaders; one third-party claim (90.19%) could not be confirmed. WebVoyager, WebArena and OSWorld V2 numbers are mostly self-reported. AndroidWorld's current leaderboard was not fetched; only the Agent S3 README figure is cited.
- Cost per task: only OpenAdapt's own benchmark and Agent S4's relative cost claim were found. No independent per-task cost data for browser-use, Stagehand or the desktop agents was fetched.
- The injection figures from the system card, crawl telemetry and the browser vendor's critic design came from secondary write-ups, not the primary sources.
- Model-weight licences were checked only for OmniParser (via its README). Fara, ShowUI, OpenCUA, EvoCUA, UI-TARS and other weights were not checked.
- Licence files not read for hyperbrowserai/HyperAgent, ucan-wg/spec, modelcontextprotocol/registry and microsoft/BIPIA (API returned NOASSERTION).
- No search was made for open MCP servers or connectors for specific HR suites beyond confirming frappe/hrms is GPL-3.0.

**Decisions needed before building**

1. macOS desktop access: PyObjC (new dependency, direct AX access) or `osascript` (no dependency, slower). This also fixes how the Accessibility permission is requested.
2. Browser: drive the user's own Chrome profile (has their sessions; highest injection exposure) or a separate profile that the user signs into per task. Recommended: separate profile.
3. Where blobs live and for how long, given that snapshots will contain personal data.
4. Grace period for the outbox, and who may shorten it.
5. Whether a VM is required for all desktop work or only for unclassified apps. A VM on Apple Silicon is free with Lima but costs disk and start-up time.
6. Whether best-of-N is ever used. Only defensible inside a disposable sandbox on tasks with no outward effects.
7. Who maintains the element classifier's word lists per language. The first customer's interfaces will include non-English labels.
8. The effect class of every existing tool in the platform has to be declared once; until then they default to irreversible and every call asks for approval.
