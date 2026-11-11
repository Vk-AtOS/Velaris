"""Model gateway: the only path from Velaris to any language or embedding model.

Providers are plain HTTP (no vendor SDKs): Anthropic, Amazon Bedrock (bearer
token), and a local Ollama server. A model is named "provider:model", e.g.
"ollama:llama3.1:8b" or "anthropic:claude-sonnet-4-6". Every call is traced
with its provider, model, sizes and duration, never the secret.

Tests and offline runs use FakeLLM, which answers from a script.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

import httpx

from velaris.intel import trace

logger = logging.getLogger("velaris.intel.llm")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
TIMEOUT_S = float(os.environ.get("VELARIS_LLM_TIMEOUT", "180"))
EMBED_DIM = 256  # size of the offline fallback embedding


class LLMError(RuntimeError):
    """A model call failed. The message never contains a credential."""


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    seconds: float


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
        r = httpx.post(url, headers=headers, json=body, timeout=TIMEOUT_S)
    except httpx.HTTPError as e:
        raise LLMError(f"request to {url.split('/')[2]} failed: {type(e).__name__}") from e
    if r.status_code >= 400:
        raise LLMError(f"{url.split('/')[2]} returned {r.status_code}: {r.text[:200]}")
    return r.json()


def _anthropic(name: str, prompt: str, system: Optional[str], max_tokens: int, temperature: float) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise LLMError("ANTHROPIC_API_KEY is not set")
    body: Dict[str, Any] = {"model": name, "max_tokens": max_tokens, "temperature": temperature,
                            "messages": [{"role": "user", "content": prompt}]}
    if system:
        body["system"] = system
    data = _post("https://api.anthropic.com/v1/messages",
                 {"x-api-key": key, "anthropic-version": "2023-06-01"}, body)
    return "".join(b.get("text", "") for b in data.get("content", []))


def _bedrock(name: str, prompt: str, system: Optional[str], max_tokens: int, temperature: float) -> str:
    token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
    if not token:
        raise LLMError("AWS_BEARER_TOKEN_BEDROCK is not set")
    region = os.environ.get("AWS_REGION", "us-east-1")
    body: Dict[str, Any] = {"messages": [{"role": "user", "content": [{"text": prompt}]}],
                            "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature}}
    if system:
        body["system"] = [{"text": system}]
    data = _post(f"https://bedrock-runtime.{region}.amazonaws.com/model/{name}/converse",
                 {"Authorization": f"Bearer {token}"}, body)
    return "".join(b.get("text", "") for b in data["output"]["message"]["content"])


def _ollama(name: str, prompt: str, system: Optional[str], max_tokens: int, temperature: float) -> str:
    body: Dict[str, Any] = {"model": name, "prompt": prompt, "stream": False,
                            "options": {"num_predict": max_tokens, "temperature": temperature}}
    if system:
        body["system"] = system
    return _post(f"{OLLAMA_URL}/api/generate", {}, body).get("response", "")


_PROVIDERS: Dict[str, Callable[..., str]] = {"anthropic": _anthropic, "bedrock": _bedrock, "ollama": _ollama}


class LLM:
    """Real gateway. Stateless; safe to share between threads."""

    def complete(self, prompt: str, *, system: Optional[str] = None, model: Optional[str] = None,
                 max_tokens: int = 1024, temperature: float = 0.2, purpose: str = "") -> Completion:
        model = model or default_model()
        provider, name = _split(model)
        if provider not in _PROVIDERS:
            raise LLMError(f"unknown provider '{provider}'")
        start = time.time()
        try:
            text = _PROVIDERS[provider](name, prompt, system, max_tokens, temperature)
        except LLMError as e:
            trace.append("llm", "complete.failed", {"model": model, "purpose": purpose, "error": str(e)})
            raise
        seconds = round(time.time() - start, 2)
        trace.append("llm", "complete", {
            "model": model, "purpose": purpose, "prompt_chars": len(prompt),
            "output_chars": len(text), "seconds": seconds,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        })
        return Completion(text=text.strip(), model=model, seconds=seconds)

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Embeddings from Ollama's nomic-embed-text; a deterministic local fallback if it is down."""
        model = os.environ.get("VELARIS_EMBED_MODEL", "nomic-embed-text")
        try:
            data = _post(f"{OLLAMA_URL}/api/embed", {}, {"model": model, "input": list(texts)})
            vectors = data["embeddings"]
            trace.append("llm", "embed", {"model": model, "count": len(texts)})
            return vectors
        except (LLMError, KeyError) as e:
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
                 max_tokens: int = 1024, temperature: float = 0.2, purpose: str = "") -> Completion:
        model = model or self.name
        self.calls.append({"prompt": prompt, "system": system, "model": model, "purpose": purpose})
        if callable(self.script):
            text = self.script(prompt, model)
        else:
            text = next((v for k, v in self.script.items() if k in prompt), None)
            if text is None:
                raise LLMError(f"FakeLLM has no scripted reply for purpose '{purpose}'")
        trace.append("llm", "complete", {"model": model, "purpose": purpose, "fake": True,
                                          "prompt_chars": len(prompt), "output_chars": len(text)})
        return Completion(text=text, model=model, seconds=0.0)

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [hashed_embedding(t) for t in texts]
