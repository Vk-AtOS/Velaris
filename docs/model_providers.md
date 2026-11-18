# Model providers, routing and OmniRoute

Text for the Confluence pages "Platform Vision and Architecture" (provider registry paragraph) and the OmniRoute
page in space SD. It is kept here so it travels with the code. The Confluence copies need an owner to paste them.

## Provider registry (KAN-11)

All model calls go through `velaris/intel/llm.py`. A model is named `provider:model`. A provider is either one of the
three built-in names, configured from the environment (`anthropic`, `bedrock`, `ollama`), or a record in the registry
(`velaris/intel/providers.py`): `{id, kind, base_url, models[], sensitivity_allowed[], enabled, allow_local, free_pool}`
plus an API key. `kind` is `openai_compatible`, `anthropic`, `bedrock` or `ollama`.

* The key is sealed with AES-256-GCM (`velaris.core.vault`) bound to the provider id. The master key
  (`VELARIS_VAULT_KEY` or `VELARIS_VAULT_KEY_FILE`) lives outside `VELARIS_DATA`. Without it a key cannot be saved or
  read (fail closed). After saving, only the last four characters are ever shown; the key is not in the trace, the
  logs, the API or any error message. Rotate replaces it.
* `sensitivity_allowed` defaults to `["public"]`. A `free_pool` provider can never be allowed `restricted`.
* State is `agents/llm_providers/providers.json` under `VELARIS_DATA`: cross-process locked, atomic, `schema_version` 1.

## Sensitivity (KAN-15)

Every call carries `public`, `internal` or `restricted`. No tag, or an unknown tag, means `restricted`. Code that has
read pay, bank, identity, health or candidate data (`access.authorize_read`) is forced to `restricted` until its request
scope ends. A provider that does not list the level is never called: the call fails with `PolicyRefused`, it is not
downgraded. Fallback chains skip such providers.

## Usage and budgets (KAN-14)

Each call is appended (sizes only, never the prompt or reply) to `agents/llm_usage/usage-YYYYMM.jsonl`, with running
totals per organisation. `usage.set_budget(org, usd=, tokens=)` or the defaults `VELARIS_ORG_BUDGET_USD` /
`VELARIS_ORG_BUDGET_TOKENS` set a monthly cap: warning at 80%, hard stop at 100% with the reason. A model with no price
in the catalogue cannot be counted against a USD budget and is refused while one is set (set the price, 0 for a model
you host). Kill switch: `VELARIS_LLM_KILL_SWITCH=1` or `usage.set_kill_switch(True)`.

## OmniRoute as an optional provider (KAN-17)

[OmniRoute](https://github.com/diegosouzapw/OmniRoute) (MIT) is a self-hosted OpenAI-compatible gateway that pools free
tiers; by default it listens on `http://localhost:20128/v1`. Its token figures are its own estimates, the terms of each
upstream provider still apply, and some free tiers use consumer-login routes that can break or breach terms.

1. Run it locally as its README describes (Docker or npm). UNVERIFIED here: this repository was prepared without
   network access and the exact image name and flags were not checked. Confirm it answers `GET http://localhost:20128/v1/models`.
2. Register it with the preset, which fixes the safe settings (`openai_compatible`, `allow_local`, `free_pool`, levels
   `public` and `internal` only):

   ```python
   from velaris.intel import providers
   providers.from_preset("omniroute", "omniroute", api_key="<its API key, if you set one>")
   ```
3. Use it only for public or internal work: documentation, research, code drafts. Pay, bank, identity, health and
   candidate data never go there: the registry refuses to store `restricted` for a free pool, and the gateway refuses the
   call. Agents that need this data must use a provider you have a retention agreement with.
4. Health: the API checks every enabled provider every 15 minutes (`VELARIS_PROVIDER_HEALTH_S`) and records outages in
   the trace. The dashboard shows a "free pool, no retention guarantee" badge on such providers (`free_pool` in the API).
5. Catalogue: `catalogue.refresh_all()` runs every 6 hours (`VELARIS_CATALOGUE_REFRESH_S`) and fills in what OmniRoute
   reports; prices stay unknown until configured.

## Tiering evaluation (KAN-19)

`python3.11 tools/tier_eval.py --models <provider:model> ... --out results.json --table results.md` runs the 20 tasks in
`velaris/intel/tiereval_tasks.json` (planner, worker, classifier, Tamil/English chat, embedding; synthetic data) on each
model and prints the table for Confluence. It needs a real model (an API key, a running Ollama, or a registered
provider). No real model has been run yet, so there is no recommendation: the default model per task class is chosen
from that table.
