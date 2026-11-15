"""The openai_compatible provider kind (KAN-12): POST {base_url}/chat/completions, /embeddings, GET /models.

Works with anything that speaks that protocol: OmniRoute (http://localhost:20128/v1), OpenRouter, vLLM,
LM Studio, a company's own gateway. Plain HTTP via httpx, no vendor SDK.

Where the request may go:
  * A public host: resolved ONCE, every address checked, the connection pinned to a checked address
    (velaris.intel.web_fetch.check_public / pinned), no redirects. Same gate as the web tools.
  * localhost or a private address: only when the provider record says allow_local. Without it the
    call is refused, so a stored base_url cannot be used to reach internal services.
The key goes only in the Authorization header. Errors name the host and the status, never the key
(and the response body is cut and scrubbed of the key before it is shown).

Tests inject `transport` and `resolver` below; production leaves both None.
"""
from __future__ import annotations

import ipaddress
import json
from typing import Any, Callable, Dict, Iterator, List, Optional
from urllib.parse import urlsplit

import httpx

from velaris.intel.errors import LLMError, Retryable
from velaris.intel.web_fetch import FetchError, check_public, pinned

MAX_BODY = 8 * 1024 * 1024
transport: Optional[httpx.BaseTransport] = None          # tests only
resolver: Optional[Callable[[str], list]] = None         # tests only


def _is_local(host: str) -> bool:
    if host.lower() in ("localhost", "host.docker.internal"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return not ip.is_global


def _scrub(text: str, key: Optional[str]) -> str:
    return text.replace(key, "[key]") if key and key in text else text


def _targets(url: str, allow_local: bool) -> List[tuple]:
    """[(url, headers, extensions)] to try, in order. Raises LLMError if the host is not allowed."""
    host = urlsplit(url).hostname or ""
    try:
        if _is_local(host):
            if not allow_local:
                raise LLMError(f"{host} is a local address and this provider is not marked allow_local")
            return [(httpx.URL(url), {}, {})]
        addresses = check_public(url, resolver) if resolver else check_public(url)
    except FetchError as e:
        raise LLMError(f"{host or 'the provider URL'} was refused: {e.reason}") from e
    return [pinned(url, a) for a in addresses]


def _send(method: str, url: str, key: Optional[str], body: Optional[Dict[str, Any]], *, allow_local: bool,
          timeout: float, stream: bool = False) -> httpx.Response:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    host = urlsplit(url).hostname
    last: Optional[Exception] = None
    with httpx.Client(transport=transport, follow_redirects=False, timeout=timeout,
                      limits=httpx.Limits(max_keepalive_connections=0)) as client:
        for target, extra, ext in _targets(url, allow_local):
            try:
                r = client.request(method, target, headers={**headers, **extra}, json=body, extensions=ext)
                if len(r.content) > MAX_BODY:
                    raise LLMError(f"{host} sent more than {MAX_BODY} bytes")
                return r
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                last = e                            # try the next checked address
            except httpx.TimeoutException as e:
                raise Retryable(f"request to {host} timed out") from e
            except httpx.HTTPError as e:
                raise LLMError(f"request to {host} failed: {type(e).__name__}") from e
    raise Retryable(f"request to {host} failed: {type(last).__name__}")


def _json(r: httpx.Response, host: str, key: Optional[str]) -> Dict[str, Any]:
    if r.status_code == 429 or r.status_code >= 500:
        raise Retryable(f"{host} returned {r.status_code}")
    if r.status_code >= 400:
        raise LLMError(f"{host} returned {r.status_code}: {_scrub(r.text[:200], key)}")
    try:
        data = r.json()
    except ValueError as e:
        raise LLMError(f"{host} returned a body that is not JSON") from e
    if not isinstance(data, dict):
        raise LLMError(f"{host} returned an unexpected JSON shape")
    return data


def _usage(data: Dict[str, Any]) -> Optional[Dict[str, int]]:
    u = data.get("usage")
    if isinstance(u, dict) and isinstance(u.get("prompt_tokens"), int) and isinstance(u.get("completion_tokens"), int):
        return {"tokens_in": u["prompt_tokens"], "tokens_out": u["completion_tokens"]}
    return None


def _sse(r: httpx.Response) -> Iterator[Dict[str, Any]]:
    for line in r.text.splitlines():
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload and payload != "[DONE]":
                try:
                    yield json.loads(payload)
                except ValueError:
                    continue


def chat(base_url: str, key: Optional[str], model: str, messages: List[Dict[str, Any]], *, allow_local: bool,
         timeout: float, max_tokens: int = 1024, temperature: float = 0.2, tools: Optional[List[Dict[str, Any]]] = None,
         tool_choice: Any = None, stream: bool = False,
         on_delta: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """One chat completion. Returns {text, tool_calls, finish_reason, usage}; tool calls pass through untouched."""
    body: Dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if tools:
        body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
    if stream:
        body["stream"] = True
        body["stream_options"] = {"include_usage": True}
    host = urlsplit(base_url).hostname or ""
    r = _send("POST", f"{base_url}/chat/completions", key, body, allow_local=allow_local, timeout=timeout)
    if stream and r.status_code < 400 and "text/event-stream" in r.headers.get("content-type", ""):
        return _from_stream(r, on_delta)
    data = _json(r, host, key)
    try:
        choice = data["choices"][0]
        msg = choice["message"]
        text = msg.get("content") or ""
        calls = msg.get("tool_calls") or []
    except (KeyError, IndexError, TypeError, AttributeError) as e:
        raise LLMError(f"{host} reply could not be read: {type(e).__name__}") from e
    if not isinstance(text, str) or not isinstance(calls, list):
        raise LLMError(f"{host} reply held no text")
    return {"text": text, "tool_calls": calls, "finish_reason": choice.get("finish_reason"), "usage": _usage(data)}


def _from_stream(r: httpx.Response, on_delta: Optional[Callable[[str], None]]) -> Dict[str, Any]:
    text, calls, finish, usage = [], {}, None, None
    for chunk in _sse(r):
        usage = _usage(chunk) or usage
        for ch in chunk.get("choices") or []:
            delta = ch.get("delta") or {}
            if delta.get("content"):
                text.append(delta["content"])
                if on_delta:
                    on_delta(delta["content"])
            for tc in delta.get("tool_calls") or []:       # fragments arrive by index: join the arguments
                cur = calls.setdefault(tc.get("index", 0), {"id": tc.get("id"), "type": "function",
                                                            "function": {"name": "", "arguments": ""}})
                fn = tc.get("function") or {}
                cur["function"]["name"] += fn.get("name") or ""
                cur["function"]["arguments"] += fn.get("arguments") or ""
            finish = ch.get("finish_reason") or finish
    return {"text": "".join(text), "tool_calls": [calls[i] for i in sorted(calls)], "finish_reason": finish,
            "usage": usage}


def embeddings(base_url: str, key: Optional[str], model: str, texts: List[str], *, allow_local: bool,
               timeout: float) -> Dict[str, Any]:
    host = urlsplit(base_url).hostname or ""
    data = _json(_send("POST", f"{base_url}/embeddings", key, {"model": model, "input": texts},
                       allow_local=allow_local, timeout=timeout), host, key)
    try:
        rows = sorted(data["data"], key=lambda d: d["index"])
        vectors = [[float(x) for x in d["embedding"]] for d in rows]
    except (KeyError, TypeError, ValueError) as e:
        raise LLMError(f"{host} embeddings could not be read: {type(e).__name__}") from e
    if len(vectors) != len(texts):
        raise LLMError(f"{host} returned {len(vectors)} embeddings for {len(texts)} texts")
    return {"vectors": vectors, "usage": _usage(data)}


def list_models(base_url: str, key: Optional[str], *, allow_local: bool, timeout: float) -> List[Dict[str, Any]]:
    """GET {base_url}/models: the raw `data` entries (each at least {"id": ...})."""
    host = urlsplit(base_url).hostname or ""
    data = _json(_send("GET", f"{base_url}/models", key, None, allow_local=allow_local, timeout=timeout), host, key)
    rows = data.get("data")
    if not isinstance(rows, list):
        raise LLMError(f"{host} model list could not be read")
    return [m for m in rows if isinstance(m, dict) and isinstance(m.get("id"), str)]
