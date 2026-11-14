# LOCAL_EMBEDDING_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/LOCAL_EMBEDDING_ENGINE/main.py` (62 lines)

## Purpose

LOCAL_EMBEDDING_ENGINE: text to vectors without sending anything off the machine, and similarity search.

method "model": the local Ollama embedding model through velaris.intel.llm
(VELARIS_EMBED_MODEL, default nomic-embed-text). If it is unreachable the
gateway falls back to the hashed vector, and the result says so.
method "hashed": velaris.intel.llm.hashed_embedding only: word and
character-trigram counts hashed into 256 numbers. Lexical, not semantic
("car" and "automobile" do not match), but deterministic and always available.
Only the local gateway is used, never a cloud provider. nearest() ranks
candidate texts by cosine similarity to a query.

## Class `LocalEmbeddingEngine`

- `__init__(name, llm)`
- `health_check()`
- `embed(text, method)` — Vectors for one text or a list. Returns vectors, dim and the method actually used.
- `nearest(query, candidates, k, method)` — The k candidates most similar to the query (cosine), best first.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.intel.llm`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_self.py`, `velaris/tests/test_layer7_offline.py`
