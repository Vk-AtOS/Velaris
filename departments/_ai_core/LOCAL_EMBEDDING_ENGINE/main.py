"""LOCAL_EMBEDDING_ENGINE: text to vectors without sending anything off the machine, and similarity search.

method "model": the local Ollama embedding model through velaris.intel.llm
(VELARIS_EMBED_MODEL, default nomic-embed-text). If it is unreachable the
gateway falls back to the hashed vector, and the result says so.
method "hashed": velaris.intel.llm.hashed_embedding only: word and
character-trigram counts hashed into 256 numbers. Lexical, not semantic
("car" and "automobile" do not match), but deterministic and always available.
Only the local gateway is used, never a cloud provider. nearest() ranks
candidate texts by cosine similarity to a query.
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit.checks import MAX_TEXT
from velaris.agentkit.results import health, invalid
from velaris.intel.llm import LLM, cosine, hashed_embedding

NAME = "LOCAL_EMBEDDING_ENGINE"
METHODS = ("model", "hashed")
MAX_BATCH = 256


def _texts(value: Any) -> Optional[List[str]]:
    many = [value] if isinstance(value, str) else value
    if not isinstance(many, list) or not 1 <= len(many) <= MAX_BATCH:
        return None
    return many if all(isinstance(t, str) and t.strip() and len(t) <= MAX_TEXT for t in many) else None


class LocalEmbeddingEngine:
    def __init__(self, name=NAME, llm: Optional[LLM] = None):
        self.name = name
        self._llm = llm or LLM()

    def health_check(self):
        return health(self.name, methods=list(METHODS))

    def embed(self, text: Any, method: str = "model") -> Dict[str, Any]:
        """Vectors for one text or a list. Returns vectors, dim and the method actually used."""
        many = _texts(text)
        if many is None or method not in METHODS:
            return invalid(f"text must be a string or 1..{MAX_BATCH} non-empty strings; method one of {METHODS}",
                           vectors=[])
        hashed = [hashed_embedding(t) for t in many]
        vectors = hashed if method == "hashed" else self._llm.embed(many)
        used = "hashed" if vectors == hashed else "model"
        return {"status": "ok", "vectors": vectors, "dim": len(vectors[0]), "method": used,
                "fell_back": method == "model" and used == "hashed"}

    def nearest(self, query: str, candidates: List[str], k: int = 3, method: str = "hashed") -> Dict[str, Any]:
        """The k candidates most similar to the query (cosine), best first."""
        pool = _texts(candidates)
        if _texts(query) is None or pool is None or not isinstance(k, int) or k < 1:
            return invalid("query must be text, candidates a list of texts and k >= 1", matches=[])
        out = self.embed([query, *pool], method=method) if len(pool) < MAX_BATCH else None
        if out is None or out["status"] != "ok":
            return invalid(f"at most {MAX_BATCH - 1} candidates", matches=[])
        q, rest = out["vectors"][0], out["vectors"][1:]
        ranked = sorted(((round(cosine(q, v), 4), i) for i, v in enumerate(rest)), key=lambda s: (-s[0], s[1]))
        return {"status": "ok", "method": out["method"],
                "matches": [{"text": pool[i], "index": i, "score": s} for s, i in ranked[:k]]}
