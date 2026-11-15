# NEURAL_CREATIVITY_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/NEURAL_CREATIVITY_ENGINE/main.py` (66 lines)

## Purpose

Neural creativity engine: a rule-based random combiner of idea pools; it is not an ML model.

NeuralCreativityEngine: add_to_pool(pool, item) adds to "objects", "actions" or "styles"
(pool name is lower-cased; False for an unknown pool or a duplicate item); generate()
picks one random item from each pool and returns object, action, style and a concept
string "<object> performing <action> in <style> style"; pool_list() returns copies of
the pools.
State: in memory only (self.pools), lost on restart; output is random, not seeded.
Failure: generate() returns {"error": "pool_empty:<pool>"} if any pool is empty; a
non-string pool name raises AttributeError.

## Class `NeuralCreativityEngine`

Velaris Neural Creativity Engine (Offline)
- NOT an ML model. Rule-based combinatorial creativity engine.
- Creates unique idea blends from predefined idea pools.

- `__init__()`
- `add_to_pool(pool, item)`
- `generate()` — Combines one random element from each pool.
- `pool_list()`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_b.py`
