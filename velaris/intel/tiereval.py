"""Model tiering evaluation harness (KAN-19).

Runs every task of a fixture file against every candidate model through the normal gateway (so the
sensitivity policy, the budget and the trace apply as always), scores each reply, and reports a table.

A task: {id, class, language (en | ta | tanglish), prompt, system?, sensitivity, kind?, tools?, expect}.
  kind "embed": `prompt` is the query, `candidates` the texts; expect {"nearest": index}.
  expect keys: contains_all, contains_any, not_contains (case-insensitive), json_keys (the reply holds a JSON
  object with these keys), json_equals ({key: value} subset), tool ({name, args_subset}), tamil_min_ratio
  (share of letters in Tamil script), max_chars.

Scores per task: content (the expectations above), tool (tool-call correctness), language (script check for
Tamil, none for English), latency, tokens and cost estimate (None = a price is not in the catalogue). A task
is passed when every applicable check holds. Language QUALITY beyond script and key phrases (fluency,
register) cannot be scored by a script: replies are kept in the results file for a human to read, and the
report says so.

A model that policy refuses for a task's sensitivity is recorded as `refused`, not as a failure of the model.
"""
from __future__ import annotations

import json
import re
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from velaris.intel import catalogue, llm, providers

TASKS_FILE = Path(__file__).with_name("tiereval_tasks.json")
TAMIL = re.compile(r"[஀-௿]")
LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
CLASSES = ("planner", "worker", "classifier", "chat", "embedding")


def load_tasks(path: Path = TASKS_FILE) -> List[Dict[str, Any]]:
    tasks = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("task ids must be unique")
    for t in tasks:
        if t["class"] not in CLASSES or t["language"] not in ("en", "ta", "tanglish") or "expect" not in t:
            raise ValueError(f"task {t['id']} is malformed")
    return tasks


def _json_in(text: str) -> Any:
    try:
        return llm.extract_json(text)
    except llm.LLMError:
        return None


def _tamil_ratio(text: str) -> float:
    letters = LETTER.findall(text)
    return len(TAMIL.findall(text)) / len(letters) if letters else 0.0


def _tool_ok(expect: Dict[str, Any], text: str, tool_calls: Sequence[Dict[str, Any]]) -> bool:
    name, args = None, None
    if tool_calls:
        fn = tool_calls[0].get("function", {})
        name = fn.get("name")
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except ValueError:
            args = None
    else:
        obj = _json_in(text)
        if isinstance(obj, dict):
            name, args = obj.get("tool") or obj.get("name"), obj.get("args") or obj.get("arguments")
    if name != expect["name"] or not isinstance(args, dict):
        return False
    return all(args.get(k) == v for k, v in expect.get("args_subset", {}).items())


def score(task: Dict[str, Any], text: str, tool_calls: Sequence[Dict[str, Any]] = ()) -> Dict[str, Any]:
    """Pure scoring of one reply: {content, tool, language, passed}; None for a check that does not apply."""
    e, low = task["expect"], text.lower()
    content = all([all(s.lower() in low for s in e.get("contains_all", [])),
                   not e.get("contains_any") or any(s.lower() in low for s in e["contains_any"]),
                   not any(s.lower() in low for s in e.get("not_contains", [])),
                   len(text) <= e.get("max_chars", 10 ** 9)])
    if "json_keys" in e or "json_equals" in e:
        obj = _json_in(text)
        content = content and isinstance(obj, dict) and all(k in obj for k in e.get("json_keys", [])) and \
            all(obj.get(k) == v for k, v in e.get("json_equals", {}).items())
    tool = _tool_ok(e["tool"], text, tool_calls) if "tool" in e else None
    language = _tamil_ratio(text) >= e["tamil_min_ratio"] if "tamil_min_ratio" in e else None
    checks = [c for c in (content, tool, language) if c is not None]
    return {"content": bool(content), "tool": tool, "language": language, "passed": all(checks)}


def _cosine_nearest(vectors: List[List[float]]) -> int:
    q, rest = vectors[0], vectors[1:]
    return max(range(len(rest)), key=lambda i: llm.cosine(q, rest[i]))


def run_task(model: str, task: Dict[str, Any], gateway: Optional[llm.LLM] = None,
             embed_with: Optional[llm.LLM] = None) -> Dict[str, Any]:
    """Run one task on one model. Never raises: a refusal or failure is part of the result."""
    gateway = gateway or llm.LLM()
    row: Dict[str, Any] = {"task": task["id"], "class": task["class"], "language": task["language"], "model": model,
                           "status": "ok", "text": "", "seconds": None, "tokens_in": None, "tokens_out": None,
                           "cost_usd": None, "score": None, "error": ""}
    level, start = task.get("sensitivity", "internal"), time.time()
    try:
        if task.get("kind") == "embed":
            import os
            old = os.environ.get("VELARIS_EMBED_MODEL")
            os.environ["VELARIS_EMBED_MODEL"] = model
            try:
                vectors = (embed_with or gateway).embed([task["prompt"], *task["candidates"]], sensitivity=level)
            finally:
                os.environ.pop("VELARIS_EMBED_MODEL") if old is None else os.environ.__setitem__("VELARIS_EMBED_MODEL", old)
            row["seconds"] = round(time.time() - start, 3)
            row["score"] = {"content": _cosine_nearest(vectors) == task["expect"]["nearest"], "tool": None,
                            "language": None}
            row["score"]["passed"] = row["score"]["content"]
            row["tokens_in"], row["tokens_out"] = max(1, sum(len(x) for x in [task["prompt"], *task["candidates"]]) // 4), 0
            entry = catalogue.get(model)                      # an embedding has no output tokens: only the input price matters
            if entry and entry["price_in_per_mtok"] is not None:
                row["cost_usd"] = row["tokens_in"] * entry["price_in_per_mtok"] / 1_000_000
            return row
        messages = ([{"role": "system", "content": task["system"]}] if task.get("system") else []) + \
                   [{"role": "user", "content": task["prompt"]}]
        provider = providers.get(model.split(":")[0])
        use_tools = bool(task.get("tools")) and provider is not None and provider.kind == "openai_compatible"
        if task.get("tools") and not use_tools:        # providers without native tools: ask for the call as JSON
            messages[-1] = {"role": "user", "content": task["prompt"] + "\n\nTools you may call (reply with JSON "
                            '{"tool": name, "args": {...}} only):\n' + json.dumps(task["tools"])}
        out = gateway.chat(messages, model=model, max_tokens=task.get("max_tokens", 600), temperature=0.0,
                           purpose=f"tiereval.{task['id']}", sensitivity=level,
                           tools=task["tools"] if use_tools else None)
        row.update(text=out.text, seconds=round(out.seconds or time.time() - start, 3))
        row["score"] = score(task, out.text, out.tool_calls)
        row["tokens_in"] = max(1, len(task["prompt"]) // 4)          # estimate; the exact counts are in the usage log
        row["tokens_out"] = max(1, len(out.text) // 4)
        row["cost_usd"] = catalogue.cost_estimate(model, row["tokens_in"], row["tokens_out"])
    except llm.PolicyRefused as e:
        row.update(status="refused", error=str(e)[:200])
    except llm.LLMError as e:
        row.update(status="error", error=str(e)[:200], seconds=round(time.time() - start, 3))
    return row


def run(models: Sequence[str], tasks: Optional[List[Dict[str, Any]]] = None,
        gateway: Optional[llm.LLM] = None) -> List[Dict[str, Any]]:
    tasks = tasks if tasks is not None else load_tasks()
    return [run_task(m, t, gateway) for m in models for t in tasks]


def summarise(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Per model: pass rate overall and per class, errors, refusals, latency (median, p95) and cost (None if any unknown)."""
    out: Dict[str, Dict[str, Any]] = {}
    for model in dict.fromkeys(r["model"] for r in results):
        rows = [r for r in results if r["model"] == model]
        ran = [r for r in rows if r["status"] == "ok"]
        by_class = {c: [r for r in ran if r["class"] == c] for c in CLASSES}
        lat = sorted(r["seconds"] for r in ran if r["seconds"] is not None)
        costs = [r["cost_usd"] for r in ran]
        out[model] = {
            "tasks": len(rows), "ran": len(ran), "errors": sum(r["status"] == "error" for r in rows),
            "refused": sum(r["status"] == "refused" for r in rows),
            "pass_rate": round(sum(r["score"]["passed"] for r in ran) / len(ran), 3) if ran else None,
            "pass_by_class": {c: round(sum(r["score"]["passed"] for r in rs) / len(rs), 3) for c, rs in by_class.items() if rs},
            "tool_call_rate": _rate([r["score"]["tool"] for r in ran]),
            "language_rate": _rate([r["score"]["language"] for r in ran]),
            "latency_median_s": round(statistics.median(lat), 3) if lat else None,
            "latency_p95_s": lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else None,
            "cost_usd": round(sum(costs), 6) if ran and all(c is not None for c in costs) else None,
        }
    return out


def _rate(flags: List[Optional[bool]]) -> Optional[float]:
    flags = [f for f in flags if f is not None]
    return round(sum(flags) / len(flags), 3) if flags else None


def markdown(summary: Dict[str, Dict[str, Any]]) -> str:
    """The results table for the Confluence page. Unknown cost reads "unknown"; language quality needs a human."""
    cell = lambda v: "unknown" if v is None else (f"{v:.0%}" if isinstance(v, float) and v <= 1 else str(v))  # noqa: E731
    head = "| Model | Pass | Planner | Worker | Classifier | Chat | Embedding | Tool calls | Language | Median s | p95 s | Cost USD | Errors | Refused |"
    lines = [head, "|" + "---|" * 14]
    for m, s in summary.items():
        pc = s["pass_by_class"]
        lines.append(f"| {m} | {cell(s['pass_rate'])} | " + " | ".join(cell(pc.get(c)) if c in pc else "-" for c in CLASSES)
                     + f" | {cell(s['tool_call_rate'])} | {cell(s['language_rate'])} | {s['latency_median_s']} | "
                       f"{s['latency_p95_s']} | {'unknown' if s['cost_usd'] is None else s['cost_usd']} | {s['errors']} | {s['refused']} |")
    lines.append("\nLanguage column is the script/phrase check only; fluency and register need a person to read the replies in the results file.")
    return "\n".join(lines)
