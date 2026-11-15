"""Model gateway: the only path from Velaris to any language or embedding model.

Providers are plain HTTP (no vendor SDKs): Anthropic, Amazon Bedrock (bearer
token), a local Ollama server, and any provider in the registry
(velaris.intel.providers), including OpenAI-compatible ones such as OmniRoute.
A model is named "provider:model", e.g. "ollama:llama3.1:8b",
"anthropic:claude-sonnet-4-6" or "omniroute:auto". Every call is traced with its
provider, model, sensitivity, sizes and duration, never the secret.

Every call passes the same gates before anything is sent, in `_invoke`:
sensitivity policy (velaris.intel.policy: no level given = restricted), then kill
switch and budget (velaris.intel.usage). It is metered afterwards, success or not.

Tests and offline runs use FakeLLM, which answers from a script.
"""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import logging
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Union

import httpx

from velaris.intel import openai_compat, policy, providers, trace, usage
from velaris.intel.errors import BudgetExceeded, LLMError, PolicyRefused, Retryable  # noqa: F401  (re-exported)

logger = logging.getLogger("velaris.intel.llm")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
TIMEOUT_S = float(os.environ.get("VELARIS_LLM_TIMEOUT", "180"))
EMBED_DIM = 256  # size of the offline fallback embedding
_call_timeout: contextvars.ContextVar[Optional[float]] = contextvars.ContextVar("velaris_llm_timeout", default=None)


@contextlib.contextmanager
def call_timeout(seconds: Optional[float]) -> Iterator[None]:
    """Model calls made inside this block (in this thread) give up after `seconds` instead of
    VELARIS_LLM_TIMEOUT. Used by callers that would rather go on without a slow model."""
    token = _call_timeout.set(seconds)
    try:
        yield
    finally:
        _call_timeout.reset(token)


class _Text(str):
    """A reply text that also carries the provider's token counts (None when it gave none)."""
    usage: Optional[Dict[str, int]] = None


def _with_usage(text: str, usage_: Optional[Dict[str, int]]) -> str:
    out = _Text(text)
    out.usage = usage_
    return out


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    seconds: float
    tool_calls: tuple = ()                 # openai_compatible only: the model's tool calls, passed through untouched


def default_model() -> str:
    """VELARIS_MODEL, else the first provider that has a credential, else local Ollama."""
    if os.environ.get("VELARIS_MODEL"):
        return os.environ["VELARIS_MODEL"]
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic:claude-sonnet-4-6"
    return "ollama:" + os.environ.get("OLLAMA_MODEL", "llama3.1:8b")


def _split(model: str) -> tuple[str, str]:
    provider, _, name = model.partition(":")
    if not name:
        raise LLMError(f"model must be 'provider:name', got '{model}'")
    return provider, name


def _post(url: str, headers: Dict[str, str], body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        r = httpx.post(url, headers=headers, json=body, timeout=_call_timeout.get() or TIMEOUT_S)
    except httpx.TimeoutException as e:
        raise Retryable(f"request to {url.split('/')[2]} timed out") from e
    except httpx.HTTPError as e:
        raise LLMError(f"request to {url.split('/')[2]} failed: {type(e).__name__}") from e
    if r.status_code == 429 or r.status_code >= 500:
        raise Retryable(f"{url.split('/')[2]} returned {r.status_code}: {r.text[:200]}")
    if r.status_code >= 400:
        raise LLMError(f"{url.split('/')[2]} returned {r.status_code}: {r.text[:200]}")
    try:
        data = r.json()
    except ValueError as e:                # an error page or truncated body with a 200 status
        raise LLMError(f"{url.split('/')[2]} returned a body that is not JSON") from e
    if not isinstance(data, dict):
        raise LLMError(f"{url.split('/')[2]} returned an unexpected JSON shape")
    return data


def _anthropic(name: str, prompt: str, system: Optional[str], max_tokens: int, temperature: float, *,
               key: Optional[str] = None, base_url: str = "") -> str:
    key = key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise LLMError("ANTHROPIC_API_KEY is not set")
    body: Dict[str, Any] = {"model": name, "max_tokens": max_tokens, "temperature": temperature,
                            "messages": [{"role": "user", "content": prompt}]}
    if system:
        body["system"] = system
    data = _post(f"{base_url or 'https://api.anthropic.com'}/v1/messages",
                 {"x-api-key": key, "anthropic-version": "2023-06-01"}, body)
    u = data.get("usage") or {}
    return _with_usage("".join(b.get("text", "") for b in data.get("content", [])),
                       {"tokens_in": u["input_tokens"], "tokens_out": u["output_tokens"]}
                       if isinstance(u.get("input_tokens"), int) and isinstance(u.get("output_tokens"), int) else None)


def _bedrock(name: str, prompt: str, system: Optional[str], max_tokens: int, temperature: float, *,
             key: Optional[str] = None, base_url: str = "") -> str:
    token = key or os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
    if not token:
        raise LLMError("AWS_BEARER_TOKEN_BEDROCK is not set")
    region = os.environ.get("AWS_REGION", "us-east-1")
    body: Dict[str, Any] = {"messages": [{"role": "user", "content": [{"text": prompt}]}],
                            "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature}}
    if system:
        body["system"] = [{"text": system}]
    data = _post(f"{base_url or f'https://bedrock-runtime.{region}.amazonaws.com'}/model/{name}/converse",
                 {"Authorization": f"Bearer {token}"}, body)
    u = data.get("usage") or {}
    return _with_usage("".join(b.get("text", "") for b in data["output"]["message"]["content"]),
                       {"tokens_in": u["inputTokens"], "tokens_out": u["outputTokens"]}
                       if isinstance(u.get("inputTokens"), int) and isinstance(u.get("outputTokens"), int) else None)


def _ollama(name: str, prompt: str, system: Optional[str], max_tokens: int, temperature: float, *,
            key: Optional[str] = None, base_url: str = "") -> str:
    body: Dict[str, Any] = {"model": name, "prompt": prompt, "stream": False,
                            "options": {"num_predict": max_tokens, "temperature": temperature}}
    if system:
        body["system"] = system
    data = _post(f"{base_url or OLLAMA_URL}/api/generate", {}, body)
    return _with_usage(data.get("response", ""),
                       {"tokens_in": data["prompt_eval_count"], "tokens_out": data["eval_count"]}
                       if isinstance(data.get("prompt_eval_count"), int) and isinstance(data.get("eval_count"), int) else None)


_PROVIDERS: Dict[str, Callable[..., str]] = {"anthropic": _anthropic, "bedrock": _bedrock, "ollama": _ollama}


def _timeout() -> float:
    return _call_timeout.get() or TIMEOUT_S


def _chat(provider: str, name: str, messages: List[Dict[str, Any]], max_tokens: int, temperature: float,
          tools: Optional[List[Dict[str, Any]]] = None, tool_choice: Any = None, stream: bool = False,
          on_delta: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Send one chat to a provider. ONLY `_invoke` calls this, after the policy and budget gates."""
    p = providers.get(provider)
    if p is not None and p.kind == "openai_compatible":
        return openai_compat.chat(p.base_url, providers.credentials(p.id), name, messages, allow_local=p.allow_local,
                                  timeout=_timeout(), max_tokens=max_tokens, temperature=temperature, tools=tools,
                                  tool_choice=tool_choice, stream=stream, on_delta=on_delta)
    if tools:
        raise LLMError(f"tool calls need an openai_compatible provider, '{provider}' is not one")
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    prompt = "\n\n".join(str(m["content"]) for m in messages if m["role"] != "system")
    kind = p.kind if p is not None else provider
    if kind not in _PROVIDERS:
        raise LLMError(f"unknown provider '{provider}'")
    extra = {"key": providers.credentials(p.id), "base_url": p.base_url} if p is not None else {}
    try:
        text = _PROVIDERS[kind](name, prompt, system, max_tokens, temperature, **extra)
    except (KeyError, IndexError, TypeError, AttributeError, ValueError) as e:     # reply shaped unlike the provider's docs
        raise LLMError(f"{provider} reply could not be read: {type(e).__name__}") from e
    if not isinstance(text, str):
        raise LLMError(f"{provider} reply held no text")
    return {"text": str(text), "tool_calls": [], "finish_reason": None, "usage": getattr(text, "usage", None)}


class LLM:
    """Real gateway. Stateless; safe to share between threads."""

    def _invoke(self, model: str, purpose: str, sensitivity: Optional[str], prompt_chars: int,
                send: Callable[[str, str], Dict[str, Any]]) -> tuple:
        """THE path to any model: policy, then budget, then the call, then metering and trace.
        `send(provider, name)` runs only after both gates passed. Returns (result, level, seconds)."""
        provider, name = _split(model)
        try:
            level = policy.authorize(provider, sensitivity)
            usage.check(model)
        except (PolicyRefused, BudgetExceeded) as e:
            trace.append("llm", "complete.refused", {"model": model, "purpose": purpose,
                                                      "sensitivity": policy.effective(sensitivity), "error": str(e)})
            raise
        start = time.time()
        try:
            result = send(provider, name)
        except LLMError as e:
            seconds = time.time() - start
            trace.append("llm", "complete.failed", {"model": model, "purpose": purpose, "sensitivity": level,
                                                     "error": str(e)})
            usage.record(model=model, purpose=purpose, sensitivity=level, status="error", seconds=seconds,
                         prompt_chars=prompt_chars, error=type(e).__name__)
            raise
        seconds = round(time.time() - start, 2)
        text = result["text"]
        usage.record(model=model, purpose=purpose, sensitivity=level, status="ok", seconds=seconds,
                     prompt_chars=prompt_chars, output_chars=len(text), usage=result.get("usage"))
        return result, level, seconds

    def chat(self, messages: List[Dict[str, Any]], *, model: Optional[str] = None, max_tokens: int = 1024,
             temperature: float = 0.2, purpose: str = "", sensitivity: Optional[str] = None,
             tools: Optional[List[Dict[str, Any]]] = None, tool_choice: Any = None, stream: bool = False,
             on_delta: Optional[Callable[[str], None]] = None) -> Completion:
        """Chat with optional tool definitions (openai_compatible providers); tool calls come back untouched."""
        model = model or default_model()
        chars = sum(len(str(m.get("content", ""))) for m in messages)
        result, level, seconds = self._invoke(
            model, purpose, sensitivity, chars,
            lambda prov, name: _chat(prov, name, messages, max_tokens, temperature, tools, tool_choice, stream, on_delta))
        trace.append("llm", "complete", {
            "model": model, "provider": model.split(":")[0], "purpose": purpose, "sensitivity": level,
            "prompt_chars": chars, "output_chars": len(result["text"]), "seconds": seconds,
            "tool_calls": len(result["tool_calls"]),
            "prompt_sha256": hashlib.sha256(json.dumps(messages, sort_keys=True, default=str).encode()).hexdigest()})
        return Completion(text=result["text"].strip(), model=model, seconds=seconds, tool_calls=tuple(result["tool_calls"]))

    def complete(self, prompt: str, *, system: Optional[str] = None, model: Optional[str] = None,
                 max_tokens: int = 1024, temperature: float = 0.2, purpose: str = "",
                 sensitivity: Optional[str] = None) -> Completion:
        """`sensitivity` is public, internal or restricted; leave it out and the call is restricted (see policy)."""
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        model = model or default_model()
        result, level, seconds = self._invoke(
            model, purpose, sensitivity, len(prompt) + len(system or ""),
            lambda prov, name: _chat(prov, name, messages, max_tokens, temperature))
        text = result["text"]
        trace.append("llm", "complete", {
            "model": model, "provider": model.split(":")[0], "purpose": purpose, "sensitivity": level,
            "prompt_chars": len(prompt), "output_chars": len(text), "seconds": seconds,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        })
        return Completion(text=text.strip(), model=model, seconds=seconds)

    def embed(self, texts: Sequence[str], *, sensitivity: Optional[str] = None) -> List[List[float]]:
        """Embeddings: from the openai_compatible provider named in VELARIS_EMBED_MODEL ("id:model") when it is
        a registered one, else Ollama's nomic-embed-text; a deterministic local fallback if that is down.
        A provider that may not see this level is not used: the offline fallback sends nothing anywhere."""
        model = os.environ.get("VELARIS_EMBED_MODEL", "nomic-embed-text")
        provider, _, name = model.partition(":")
        p = providers.get(provider) if name else None
        try:
            if p is not None and p.kind == "openai_compatible":
                level = policy.authorize(provider, sensitivity)
                usage.check(model)
                start = time.time()
                try:
                    out = openai_compat.embeddings(p.base_url, providers.credentials(p.id), name, list(texts),
                                                   allow_local=p.allow_local, timeout=_timeout())
                except LLMError as e:
                    usage.record(model=model, purpose="embed", sensitivity=level, status="error",
                                 seconds=time.time() - start, prompt_chars=sum(map(len, texts)), error=type(e).__name__)
                    raise
                usage.record(model=model, purpose="embed", sensitivity=level, status="ok", seconds=time.time() - start,
                             prompt_chars=sum(map(len, texts)), usage=out["usage"])
                trace.append("llm", "embed", {"model": model, "count": len(texts), "sensitivity": level})
                return out["vectors"]
            level = policy.authorize("ollama", sensitivity)
            usage.check(f"ollama:{model}")
            data = _post(f"{OLLAMA_URL}/api/embed", {}, {"model": model, "input": list(texts)})
            vectors = data["embeddings"]
            usage.record(model=f"ollama:{model}", purpose="embed", sensitivity=level, status="ok", seconds=0.0,
                         prompt_chars=sum(map(len, texts)))
            trace.append("llm", "embed", {"model": model, "count": len(texts), "sensitivity": level})
            return vectors
        except (BudgetExceeded, PolicyRefused):
            raise
        except (LLMError, KeyError, TypeError) as e:
            logger.warning("embedding model unavailable (%s); using the offline fallback", e)
            trace.append("llm", "embed.fallback", {"count": len(texts)})
            return [hashed_embedding(t) for t in texts]


def hashed_embedding(text: str, dim: int = EMBED_DIM) -> List[float]:
    """Offline embedding: hashed word and character-trigram counts, L2-normalised.

    ponytail: lexical, not semantic ("car" and "automobile" are unrelated here).
    It keeps memory and retrieval working without any model; a real embedding
    model replaces it whenever one is reachable.
    """
    vec = [0.0] * dim
    words = re.findall(r"[a-z0-9]+", text.lower())
    grams = words + [w[i:i + 3] for w in words for i in range(max(0, len(w) - 2))]
    for g in grams:
        h = int.from_bytes(hashlib.blake2b(g.encode(), digest_size=8).digest(), "big")
        vec[h % dim] += 1.0 if (h >> 63) else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def extract_json(text: str) -> Any:
    """Parse the first JSON object or array in a model reply; raise LLMError if there is none.

    Models wrap JSON in prose or code fences; a reply that still does not parse
    is an error for the caller to handle, never silently treated as empty.
    """
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidates = [fenced.group(1)] if fenced else []
    start = min((i for i in (text.find("{"), text.find("[")) if i != -1), default=-1)
    if start != -1:
        end = max(text.rfind("}"), text.rfind("]"))
        candidates.append(text[start:end + 1])
    for c in candidates:
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    raise LLMError("model reply contained no valid JSON")


class FakeLLM(LLM):
    """Scripted stand-in for tests. `script` maps a substring of the prompt (or a
    callable taking prompt, model) to the reply; the first match wins."""

    def __init__(self, script: Union[Dict[str, str], Callable[[str, str], str]], *, name: str = "fake:model"):
        self.script, self.name, self.calls = script, name, []  # type: ignore[var-annotated]

    def complete(self, prompt: str, *, system: Optional[str] = None, model: Optional[str] = None,
                 max_tokens: int = 1024, temperature: float = 0.2, purpose: str = "",
                 sensitivity: Optional[str] = None) -> Completion:
        model = model or self.name
        self.calls.append({"prompt": prompt, "system": system, "model": model, "purpose": purpose,
                           "sensitivity": sensitivity})
        if callable(self.script):
            text = self.script(prompt, model)
        else:
            text = next((v for k, v in self.script.items() if k in prompt), None)
            if text is None:
                raise LLMError(f"FakeLLM has no scripted reply for purpose '{purpose}'")
        trace.append("llm", "complete", {"model": model, "purpose": purpose, "fake": True,
                                          "prompt_chars": len(prompt), "output_chars": len(text)})
        return Completion(text=text, model=model, seconds=0.0)

    def embed(self, texts: Sequence[str], *, sensitivity: Optional[str] = None) -> List[List[float]]:
        return [hashed_embedding(t) for t in texts]
