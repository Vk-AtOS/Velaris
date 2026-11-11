"""Import and analyse an n8n-style workflow export.

A company's existing automation usually lives on a workflow board. Before an
agentic replacement is proposed, the platform has to understand what the board
does. The pipeline here is deterministic: no model, no network, nothing is
executed and no n8n expression is evaluated.

  1. load()                  JSON -> validated Workflow (unique node names, no
                             dangling connections, size caps for hostile files).
  2. graph                   `main` edges are control flow (forward and inverse
                             adjacency); every other connection type (`ai_tool`,
                             `ai_languageModel`, ...) is an attachment of a
                             sub-node to an agent node, not a step.
  3. analyse()               triggers, execution order, loops, branches, merges,
                             unreachable and disabled nodes, error handling,
                             credential references, external systems.
  4. to_plan()               the same process as an ordered, readable step list.
  5. required_permissions()  what a human approves before activation.

Parameter values are never echoed raw: the few that are summarised go through
guard.redact, expressions are replaced by a placeholder, URLs are reduced to
their host, and every returned structure is checked for secret-looking text.
"""
from __future__ import annotations

import heapq
import json
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from velaris.intel import guard

MAX_JSON_CHARS = 20_000_000  # raw export size accepted before parsing
MAX_NODES = 5_000
MAX_INPUT_INDEX = 1_000
MAX_SLOTS = 100_000          # output slots plus the connections inside them
MAX_CYCLES_REPORTED = 100    # counts.cycles still holds the true total
_SECRET_KINDS = {"aws_access_key", "api_key", "private_key", "jwt"}

# Node types (after _base) that do their work inside the workflow engine.
# Anything not listed is assumed to touch an external system.
# ponytail: a code node is listed as internal although custom code can call out;
# inspect its source if that distinction starts to matter.
_INTERNAL = {
    "if", "switch", "merge", "set", "editfields", "code", "function", "functionitem", "noop",
    "wait", "splitinbatches", "filter", "sort", "limit", "itemlists", "aggregate",
    "removeduplicates", "splitout", "summarize", "datetime", "crypto", "html", "markdown", "xml",
    "comparedatasets", "renamekeys", "stickynote", "manual", "schedule", "cron", "interval",
    "start", "webhook", "form", "chat", "error", "respondtowebhook", "stopanderror",
    "executeworkflow", "workflow", "agent", "chainllm", "bufferwindow", "calculator",
    "outputparserstructured",
}
_SUB_NODE_PREFIXES = ("lmChat", "lm", "embeddings", "vectorStore", "memory", "tool")
_PHRASES = {
    "if": "branches on a condition", "switch": "routes items to one of several outputs",
    "merge": "merges incoming branches", "set": "sets fields", "editfields": "sets fields",
    "code": "runs custom code", "function": "runs custom code", "wait": "waits before continuing",
    "noop": "does nothing (pass-through)", "agent": "runs an AI agent",
    "splitinbatches": "loops over items in batches", "filter": "filters items",
    "respondtowebhook": "responds to the webhook caller",
    "stopanderror": "stops the workflow with an error", "executeworkflow": "runs another workflow",
}
_HTTP_METHODS = {"GET": "read", "HEAD": "read", "OPTIONS": "read", "POST": "write", "PUT": "write",
                 "PATCH": "write", "DELETE": "delete"}
# Checked in this order; the first matching prefix wins.
_OPERATIONS = (
    ("send", ("send", "reply", "post", "publish", "notify")),
    ("write", ("create", "update", "upsert", "append", "add", "insert", "write", "upload", "edit",
               "set", "move", "copy", "rename", "archive")),
    ("read", ("get", "list", "search", "read", "lookup", "download", "select", "find", "count")),
)


class WorkflowError(ValueError):
    """The export is malformed, hostile, or would leak a secret."""


class Node(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    typeVersion: float = 1
    parameters: Dict[str, Any] = Field(default_factory=dict)
    credentials: Dict[str, Any] = Field(default_factory=dict)
    disabled: bool = False
    onError: Optional[str] = None
    continueOnFail: bool = False     # older exports, before onError existed
    retryOnFail: bool = False
    maxTries: Optional[int] = None
    waitBetweenTries: Optional[int] = None


class Edge(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    kind: str        # "main" or an attachment type such as "ai_tool"
    output: int
    input: int


class Workflow(BaseModel):
    name: str = ""
    nodes: List[Node]
    edges: List[Edge]
    settings: Dict[str, Any] = Field(default_factory=dict)

    def _adjacency(self, inverse: bool) -> Dict[str, List[str]]:
        adj: Dict[str, Dict[str, None]] = {n.name: {} for n in self.nodes}   # dict = ordered set
        for e in self.edges:
            if e.kind == "main":
                a, b = (e.target, e.source) if inverse else (e.source, e.target)
                adj[a][b] = None
        return {name: list(targets) for name, targets in adj.items()}

    def forward(self) -> Dict[str, List[str]]:
        """node -> nodes it hands data to, over `main` edges only."""
        return self._adjacency(inverse=False)

    def inverse(self) -> Dict[str, List[str]]:
        """node -> nodes it receives data from, over `main` edges only."""
        return self._adjacency(inverse=True)

    def main_edges(self) -> Set[Tuple[str, str]]:
        """The designed control flow as (from, to) pairs, e.g. for process_mining.conformance."""
        return {(e.source, e.target) for e in self.edges if e.kind == "main"}

    def attachments(self) -> Dict[str, List[Dict[str, str]]]:
        """agent node -> the sub-nodes (models, tools, memory) attached to it."""
        types = {n.name: n.type for n in self.nodes}
        out: Dict[str, List[Dict[str, str]]] = {}
        for e in self.edges:
            if e.kind != "main":
                out.setdefault(e.target, []).append(
                    {"node": e.source, "kind": e.kind, "type": types[e.source]})
        return out


def load(data: Union[dict, str]) -> Workflow:
    """Parse and validate an export. Raises WorkflowError on anything malformed."""
    if isinstance(data, str):
        if len(data) > MAX_JSON_CHARS:
            raise WorkflowError(f"export too large: {len(data)} characters > {MAX_JSON_CHARS}")
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            raise WorkflowError(f"not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise WorkflowError("a workflow must be a JSON object")
    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, list):
        raise WorkflowError("'nodes' must be a list")
    if len(raw_nodes) > MAX_NODES:
        raise WorkflowError(f"too many nodes: {len(raw_nodes)} > {MAX_NODES}")
    nodes: List[Node] = []
    names: Set[str] = set()
    for i, raw in enumerate(raw_nodes):
        try:
            node = Node.model_validate(raw)
        except ValidationError as e:
            err = e.errors()[0]    # location and message only: never the offending value
            raise WorkflowError(f"node {i} is invalid at {list(err['loc'])}: {err['msg']}") from e
        if node.name in names:
            raise WorkflowError(f"duplicate node name: {node.name!r}")
        names.add(node.name)
        nodes.append(node)
    settings, connections = data.get("settings"), data.get("connections")
    return Workflow(name=str(data.get("name") or ""), nodes=nodes,
                    edges=_load_edges({} if connections is None else connections, names),
                    settings=settings if isinstance(settings, dict) else {})


def _load_edges(connections: Any, names: Set[str]) -> List[Edge]:
    if not isinstance(connections, dict):
        raise WorkflowError("'connections' must be an object keyed by source node name")
    edges: List[Edge] = []
    slots = 0
    for source, by_kind in connections.items():
        if source not in names:
            raise WorkflowError(f"connection source {source!r} is not a node")
        if not isinstance(by_kind, dict):
            raise WorkflowError(f"connections of {source!r} must be an object")
        for kind, outputs in by_kind.items():
            if not isinstance(outputs, list):
                raise WorkflowError(f"{source!r}.{kind} must be a list of output slots")
            for output, slot in enumerate(outputs):
                if slot is not None and not isinstance(slot, list):
                    raise WorkflowError(f"{source!r}.{kind}[{output}] must be a list or null")
                slots += 1 + len(slot or ())
                if slots > MAX_SLOTS:
                    raise WorkflowError(f"too many connection slots: more than {MAX_SLOTS}")
                for conn in slot or ():
                    target = conn.get("node") if isinstance(conn, dict) else None
                    if not isinstance(target, str) or target not in names:
                        raise WorkflowError(f"{source!r} connects to a missing node: {target!r}")
                    index = conn.get("index", 0)
                    if type(index) is not int or not 0 <= index <= MAX_INPUT_INDEX:
                        raise WorkflowError(
                            f"{source!r} -> {target!r}: input index must be 0..{MAX_INPUT_INDEX}")
                    edges.append(Edge(source=source, target=target, kind=kind, output=output,
                                      input=index))
    return edges


# ---- reading a node without running it -------------------------------------------------------

def _short(node_type: str) -> str:
    return node_type.rsplit(".", 1)[-1]


def _base(node_type: str) -> str:
    """'n8n-nodes-base.slackTrigger' -> 'slack'; '...langchain.lmChatOpenAi' -> 'openai'."""
    short = _short(node_type)
    for prefix in _SUB_NODE_PREFIXES:
        if short.startswith(prefix) and short[len(prefix):len(prefix) + 1].isupper():
            short = short[len(prefix):]
            break
    for suffix in ("Trigger", "Tool"):
        if short.endswith(suffix) and len(short) > len(suffix):
            short = short[:-len(suffix)]
    return short.lower()


def _trigger_kind(node: Node) -> Optional[str]:
    """webhook | schedule | manual | poll | event, or None when the node does not start a run."""
    short = _short(node.type).lower()
    if not (short.endswith("trigger") or short in ("webhook", "cron", "interval", "start",
                                                   "emailreadimap")):
        return None
    if "webhook" in short or short.startswith(("form", "chat")):
        return "webhook"
    if any(word in short for word in ("schedule", "cron", "interval")):
        return "schedule"
    if "manual" in short or short == "start":
        return "manual"
    # ponytail: the type name does not say whether an app trigger polls or is pushed to;
    # only the obvious polling types are named, the rest are reported as "event".
    return "poll" if any(word in short for word in ("imap", "rss", "poll")) else "event"


def _literal(value: Any) -> Optional[str]:
    """A parameter as plain text, or None if it is absent, structured or an expression."""
    if isinstance(value, dict):          # resource locator: {"__rl": true, "value": ..., "mode": ...}
        value = value.get("value")
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    text = str(value).strip()
    return None if not text or text.startswith("=") else text


def _safe(text: str) -> str:
    return guard.redact(text)[0][:120]


def _host(url: Any) -> Optional[str]:
    text = _literal(url)
    if not text:
        return None
    try:
        return urlsplit(text).hostname
    except ValueError:
        return None


def _system(node: Node) -> Optional[str]:
    """Readable name of the external system a node touches, or None for engine-internal nodes."""
    base = _base(node.type)
    if base in _INTERNAL:
        return None
    if base == "httprequest":
        return _safe(_host(node.parameters.get("url")) or "http")
    return _safe(base)


def _http_method(node: Node) -> Optional[str]:
    """The literal HTTP method of an HTTP node, upper-cased, or None when it cannot be known.

    n8n leaves a parameter out of the export when it holds its default, and the HTTP
    Request node's default method is GET, so a plain HTTP Request node with no method
    is a GET. That default is assumed only for that exact node type and only when no
    method key is present at all (older node versions call the key `requestMethod`);
    an expression, an empty value or any other HTTP-flavoured node stays unknown.
    """
    for key in ("method", "requestMethod"):
        if key in node.parameters:
            return (_literal(node.parameters[key]) or "").upper() or None
    return "GET" if _short(node.type) == "httpRequest" else None


def _operation(node: Node) -> str:
    """read | write | send | delete | execute. Anything not recognised is 'execute'."""
    if _base(node.type) == "httprequest":
        return _HTTP_METHODS.get(_http_method(node) or "", "execute")
    op = (_literal(node.parameters.get("operation")) or "").lower()
    if "delete" in op or "remove" in op:
        return "delete"
    for name, prefixes in _OPERATIONS:
        if op.startswith(prefixes):
            return name
    return "read" if not op and _trigger_kind(node) else "execute"


def _credentials(node: Node) -> List[Dict[str, str]]:
    """Credential references (type + display name). Other keys of a credential are ignored."""
    return [{"type": _safe(str(ctype)),
             "name": _safe(str(ref.get("name") or "")) if isinstance(ref, dict) else ""}
            for ctype, ref in sorted(node.credentials.items())]


def _error_handling(node: Node) -> Dict[str, Any]:
    on_error = node.onError or ("continueRegularOutput" if node.continueOnFail else "stopWorkflow")
    return {"node": node.name, "on_error": on_error, "retry": node.retryOnFail,
            "max_tries": node.maxTries if node.retryOnFail else None,
            "wait_between_tries_ms": node.waitBetweenTries if node.retryOnFail else None,
            "handled": node.retryOnFail or on_error != "stopWorkflow"}


def _describe(node: Node) -> str:
    base, p, kind = _base(node.type), node.parameters, _trigger_kind(node)
    if kind == "webhook":
        path = _literal(p.get("path"))
        phrase = "starts when a webhook is called" + (f" (/{path.lstrip('/')})" if path else "")
    elif kind:
        phrase = {"schedule": "starts on a schedule", "manual": "starts when run manually"}.get(
            kind, f"starts on a {base} event")
    elif base == "httprequest":
        method = _http_method(node) or "an unspecified method on"
        phrase = f"calls {method} {_host(p.get('url')) or 'a dynamic URL'}"
    elif base in _PHRASES:
        phrase = _PHRASES[base]
    elif base in _INTERNAL:
        phrase = f"runs a {base} step"
    else:
        what = " ".join(filter(None, (_literal(p.get("resource")), _literal(p.get("operation")))))
        target = next(filter(None, (_literal(p.get(k)) for k in ("channel", "table", "path"))), None)
        phrase = f"{base}: {what or 'unspecified operation'}" + (f" ({target})" if target else "")
    return ("(disabled) " if node.disabled else "") + _safe(phrase)


def _checked(out: Any) -> Any:
    """Refuse to return anything that still contains a secret-looking value."""
    kinds = _SECRET_KINDS & guard.redact(json.dumps(out, default=str))[1].keys()
    if kinds:
        raise WorkflowError(f"output would contain secret-looking values: {sorted(kinds)}; "
                            "remove them from node names, types or credential names")
    return out


# ---- graph analysis ---------------------------------------------------------------------------

def _steps(wf: Workflow) -> List[str]:
    """Nodes that are steps of the process: not canvas notes, not sub-nodes attached to an agent."""
    wired = {name for edge in wf.main_edges() for name in edge}
    sub_nodes = {e.source for e in wf.edges if e.kind != "main"}
    return [n.name for n in wf.nodes
            if n.name in wired or not (n.name in sub_nodes or _base(n.type) == "stickynote")]


def _enabled_triggers(wf: Workflow) -> List[str]:
    return [n.name for n in wf.nodes if _trigger_kind(n) and not n.disabled]


def _loops(wf: Workflow, steps: List[str], fwd: Dict[str, List[str]]) -> List[List[str]]:
    """Depth-first walk from the triggers; an edge back onto the current path closes a loop.

    Each loop is the node path [entry, ..., last]; (last, entry) is the edge that closes it.
    """
    inv = wf.inverse()
    roots = _enabled_triggers(wf) + [s for s in steps if not inv[s]] + steps
    depth: Dict[str, int] = {}       # position on the current path
    done: Set[str] = set()
    loops: List[List[str]] = []
    for root in roots:
        if root in depth or root in done:
            continue
        depth[root] = 0
        path, stack = [root], [iter(fwd[root])]
        while stack:
            nxt = next(stack[-1], None)
            if nxt is None:
                stack.pop()
                finished = path.pop()
                del depth[finished]
                done.add(finished)
            elif nxt in depth:
                loops.append(path[depth[nxt]:] if len(loops) < MAX_CYCLES_REPORTED else [nxt, path[-1]])
            elif nxt not in done:
                depth[nxt] = len(path)
                path.append(nxt)
                stack.append(iter(fwd[nxt]))
    return loops


def _order(wf: Workflow) -> Tuple[List[str], List[List[str]]]:
    """Topological order of the steps, ignoring the edges that close loops. Ties: file order."""
    steps, fwd = _steps(wf), wf.forward()
    loops = _loops(wf, steps, fwd)
    closing = {(loop[-1], loop[0]) for loop in loops}
    index = {name: i for i, name in enumerate(steps)}
    waiting = {name: 0 for name in steps}
    for name in steps:
        for nxt in fwd[name]:
            if (name, nxt) not in closing:
                waiting[nxt] += 1
    ready = [index[name] for name in steps if not waiting[name]]
    heapq.heapify(ready)
    order: List[str] = []
    while ready:
        name = steps[heapq.heappop(ready)]
        order.append(name)
        for nxt in fwd[name]:
            if (name, nxt) not in closing:
                waiting[nxt] -= 1
                if not waiting[nxt]:
                    heapq.heappush(ready, index[nxt])
    return order, loops


def _branches(wf: Workflow) -> Dict[str, List[Dict[str, Any]]]:
    """node -> its used outputs, for nodes with more than one used output."""
    by_node: Dict[str, Dict[int, List[str]]] = {}
    for e in wf.edges:
        if e.kind == "main":
            by_node.setdefault(e.source, {}).setdefault(e.output, []).append(e.target)
    nodes = {n.name: n for n in wf.nodes}
    out: Dict[str, List[Dict[str, Any]]] = {}
    for name, outputs in by_node.items():
        if len(outputs) < 2:
            continue
        node, last = nodes[name], max(outputs)
        out[name] = []
        for i in sorted(outputs):
            if _base(node.type) == "if" and i < 2:
                label = ("true", "false")[i]
            elif node.onError == "continueErrorOutput" and i == last:
                label = "error"
            else:
                label = f"output {i}"
            out[name].append({"output": i, "label": label, "targets": outputs[i]})
    return out


def _reachable(wf: Workflow) -> Set[str]:
    """Everything an enabled trigger can lead to, including sub-nodes attached along the way."""
    fwd, attached = wf.forward(), wf.attachments()
    seen = set(_enabled_triggers(wf))
    queue = deque(seen)
    while queue:
        name = queue.popleft()
        for nxt in fwd[name] + [a["node"] for a in attached.get(name, ())]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def analyse(wf: Workflow) -> Dict[str, Any]:
    """Everything the platform needs to know about a workflow, as plain JSON-serialisable data."""
    order, loops = _order(wf)
    inv, branches, reachable = wf.inverse(), _branches(wf), _reachable(wf)
    handling = [_error_handling(n) for n in wf.nodes]
    handled = {h["node"] for h in handling if h["handled"]}
    credentials: Dict[Tuple[str, str], List[str]] = {}
    systems: Dict[str, List[str]] = {}
    for n in wf.nodes:
        for cred in _credentials(n):
            credentials.setdefault((cred["type"], cred["name"]), []).append(n.name)
        system = _system(n)
        if system:
            systems.setdefault(system, []).append(n.name)
    report = {
        "name": wf.name,
        "triggers": [{"node": n.name, "kind": _trigger_kind(n), "disabled": n.disabled}
                     for n in wf.nodes if _trigger_kind(n)],
        "execution_order": order,
        "cycles": loops[:MAX_CYCLES_REPORTED],
        "branch_points": [{"node": name, "outputs": outs} for name, outs in branches.items()],
        "merge_points": [{"node": name, "inputs": sources} for name, sources in inv.items()
                         if len(sources) > 1],
        "unreachable": [n.name for n in wf.nodes
                        if n.name not in reachable and _base(n.type) != "stickynote"],
        "disabled": [n.name for n in wf.nodes if n.disabled],
        "error_handling": handling,
        "error_workflow": bool(wf.settings.get("errorWorkflow")),
        "unhandled_external": [n.name for n in wf.nodes
                               if _system(n) and not n.disabled and n.name not in handled],
        "credentials": [{"type": t, "name": name, "nodes": nodes}
                        for (t, name), nodes in sorted(credentials.items())],
        "external_systems": [{"system": s, "nodes": nodes} for s, nodes in sorted(systems.items())],
        "attachments": wf.attachments(),
    }
    report["counts"] = {
        "nodes": len(wf.nodes), "steps": len(order),
        "main_edges": sum(e.kind == "main" for e in wf.edges),
        "attachment_edges": sum(e.kind != "main" for e in wf.edges),
        "cycles": len(loops),
        "external_nodes": sum(len(nodes) for nodes in systems.values()),
        **{key: len(report[key]) for key in ("triggers", "branch_points", "merge_points",
                                             "unreachable", "disabled", "unhandled_external",
                                             "credentials", "external_systems")},
    }
    return _checked(report)


def to_plan(wf: Workflow) -> List[Dict[str, Any]]:
    """The process as numbered steps a person or a model can read. Step numbers follow analyse()."""
    order, _ = _order(wf)
    step = {name: i for i, name in enumerate(order, start=1)}
    nodes = {n.name: n for n in wf.nodes}
    fwd, inv, branches, attached = wf.forward(), wf.inverse(), _branches(wf), wf.attachments()
    return _checked([{
        "step": step[name],
        "node": name,
        "type": nodes[name].type,
        "does": _describe(nodes[name]),
        "inputs": sorted(step[source] for source in inv[name]),
        "next": sorted(step[target] for target in fwd[name]),
        "branches": [{"label": b["label"], "to": sorted(step[t] for t in b["targets"])}
                     for b in branches.get(name, ())],
        "uses": [f"{a['node']} ({a['kind']})" for a in attached.get(name, ())],
    } for name in order])


def required_permissions(wf: Workflow) -> List[Dict[str, Any]]:
    """One row per external node and credential: what a human approves before activation.

    Disabled nodes are listed too (flagged), because enabling one later is a one-click change.
    """
    rows: List[Dict[str, Any]] = []
    for n in wf.nodes:
        system = _system(n)
        if system:
            for cred in _credentials(n) or [None]:
                rows.append({"node": n.name, "system": system, "operation": _operation(n),
                             "credential": cred, "disabled": n.disabled})
    return _checked(rows)
