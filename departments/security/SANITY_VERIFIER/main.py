"""SANITY_VERIFIER: last check on an agent's output, and a check of the runtime configuration.

verify(output) inspects a result before it is released and reports findings with
a severity. final_safe_output is True only when nothing is "high" or "critical":

  critical   not an object; text that the injection guard blocks
  high       any object inside the output (the output itself included) whose
             "status" is not "ok" - an upstream stage that reported no_schema,
             no_constraints, an error or anything else was not checked, so the
             result is not released. A payload that legitimately carries its own
             non-ok "status" field must be verified on its own, not inside a stage result.
  high       not JSON (or holds NaN/Infinity); larger than MAX_BYTES; nested deeper
             than MAX_DEPTH (an output over MAX_BYTES is rejected without a content
             scan; anything within it is scanned in full); a credential in the text (API key, private key, JWT,
             AWS key); instruction-like text scored "high" by the guard; a field
             missing from, or of the wrong type for, the caller's schema
  medium     personal identifiers in the text (email, phone, PAN, Aadhaar, card ...)
  low        faintly instruction-like text

Text screening is velaris.intel.guard's (heuristic: it can miss novel phrasing).
This verifier judges form and content hygiene; it cannot tell whether an answer is true.

verify_config(env) checks the settings Velaris reads from the environment
(VELARIS_DATA, VELARIS_MODEL, VELARIS_LLM_TIMEOUT, OLLAMA_URL and provider
credentials) for values that would break or weaken a run.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
from typing import Any, Dict, Iterator, List, Mapping, Optional

from velaris.intel import guard

logger = logging.getLogger("SANITY_VERIFIER")
NAME = "SANITY_VERIFIER"
MAX_BYTES = 1024 * 1024
MAX_DEPTH = 40
BLOCKING = ("high", "critical")
CREDENTIAL_KINDS = ("aws_access_key", "api_key", "private_key", "jwt")
SCHEMA_TYPES = {"str": str, "int": int, "number": (int, float), "bool": bool, "list": list, "dict": dict}
PROVIDER_CREDENTIAL = {"anthropic": "ANTHROPIC_API_KEY", "bedrock": "AWS_BEARER_TOKEN_BEDROCK", "ollama": None}


def _finding(severity: str, check: str, detail: str) -> Dict[str, str]:
    return {"severity": severity, "check": check, "detail": detail}


def _not_ok(value: Any, path: str = "$", depth: int = 0) -> Iterator[Dict[str, str]]:
    """Findings for every object under `value` that carries a status other than "ok"."""
    if depth > MAX_DEPTH:
        return
    if isinstance(value, dict):
        status = value.get("status")
        if "status" in value and status != "ok":
            reason = value.get("reason")
            detail = f"{path}: status {status!r}" + (f" ({str(reason)[:160]})" if reason else "")
            yield _finding("high", "upstream_not_ok", detail)
        for k, v in value.items():
            yield from _not_ok(v, f"{path}.{k}", depth + 1)
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            yield from _not_ok(v, f"{path}[{i}]", depth + 1)


def _strings(value: Any, depth: int = 0) -> Iterator[str]:
    """Every string in a JSON value, keys included. Raises RecursionError past MAX_DEPTH."""
    if depth > MAX_DEPTH:
        raise RecursionError("too deep")
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from _strings(v, depth + 1)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings(v, depth + 1)


class SanityVerifier:
    def __init__(self, name: str = NAME) -> None:
        self.name = name

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def verify(self, constrained: dict, schema: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Findings for one output. `schema` is {field: one of SCHEMA_TYPES} of required top-level fields."""
        if schema is not None and (not isinstance(schema, dict) or not all(t in SCHEMA_TYPES for t in schema.values())):
            return {"status": "invalid_input", "final_safe_output": False,
                    "reason": f"schema must map field names to one of {', '.join(SCHEMA_TYPES)}", "findings": []}
        findings: List[Dict[str, str]] = []
        if not isinstance(constrained, dict):
            findings.append(_finding("critical", "not_an_object", f"output is {type(constrained).__name__}, not an object"))
            return self._result(findings)
        try:
            text = "\n".join(_strings(constrained))
            size = len(json.dumps(constrained, allow_nan=False).encode())
        except RecursionError:
            return self._result([_finding("high", "too_deep", f"nested deeper than {MAX_DEPTH} levels")])
        except (TypeError, ValueError) as e:
            return self._result([_finding("high", "not_json", f"cannot be serialised as JSON: {str(e)[:120]}")])
        findings += list(_not_ok(constrained))
        if size > MAX_BYTES:            # unsafe already; the text is not scanned past the cap
            findings.append(_finding("high", "too_large", f"{size} bytes; the limit is {MAX_BYTES}"))
            return self._result(findings)
        # The whole text is scanned: it is no longer than the JSON, which is within MAX_BYTES.
        scan = guard.scan(text, source=NAME)
        if scan.level != "none":
            severity = {"block": "critical", "high": "high", "low": "low"}[scan.level]
            findings.append(_finding(severity, "instruction_like_text", ", ".join(f["rule"] for f in scan.findings)))
        kinds = guard.redact(text)[1]
        credentials = sorted(k for k in kinds if k in CREDENTIAL_KINDS)
        personal = sorted(k for k in kinds if k not in CREDENTIAL_KINDS)
        if credentials:
            findings.append(_finding("high", "credential_in_output", ", ".join(credentials)))
        if personal:
            findings.append(_finding("medium", "personal_data", ", ".join(personal)))
        for field, type_name in (schema or {}).items():
            value = constrained.get(field)
            wrong = isinstance(value, bool) and type_name in ("int", "number")
            if field not in constrained:
                findings.append(_finding("high", "missing_field", field))
            elif wrong or not isinstance(value, SCHEMA_TYPES[type_name]):
                findings.append(_finding("high", "wrong_type", f"{field} should be {type_name}"))
        return self._result(findings)

    @staticmethod
    def _result(findings: List[Dict[str, str]]) -> Dict[str, Any]:
        safe = not any(f["severity"] in BLOCKING for f in findings)
        result = {"status": "ok" if safe else "rejected", "final_safe_output": safe, "findings": findings}
        if not safe:
            result["reason"] = "; ".join(f"{f['check']}: {f['detail']}" for f in findings if f["severity"] in BLOCKING)[:1000]
        return result

    def verify_config(self, env: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
        """Findings about the environment settings Velaris reads. `env` defaults to this process's environment."""
        env = os.environ if env is None else env
        if not isinstance(env, Mapping) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
            return {"status": "invalid_input", "sane": False, "reason": "env must map names to text", "findings": []}
        findings = []
        data = env.get("VELARIS_DATA", "")
        if data and not os.path.isabs(data):
            findings.append(_finding("medium", "VELARIS_DATA", "relative path: state moves with the working directory"))
        if data and os.path.isdir(data) and os.stat(data).st_mode & 0o077:
            findings.append(_finding("high", "VELARIS_DATA", "data directory is readable by other users"))
        timeout = env.get("VELARIS_LLM_TIMEOUT")
        if timeout is not None:
            try:
                if not 0 < float(timeout) < float("inf"):
                    raise ValueError(timeout)
            except ValueError:
                findings.append(_finding("high", "VELARIS_LLM_TIMEOUT", "must be a positive number of seconds"))
        model = env.get("VELARIS_MODEL")
        if model is not None:
            provider, _, name = model.partition(":")
            if provider not in PROVIDER_CREDENTIAL or not name:
                findings.append(_finding("high", "VELARIS_MODEL", "must be 'provider:name' with provider anthropic, bedrock or ollama"))
            elif PROVIDER_CREDENTIAL[provider] and not env.get(PROVIDER_CREDENTIAL[provider]):
                findings.append(_finding("high", "VELARIS_MODEL", f"{provider} is selected but {PROVIDER_CREDENTIAL[provider]} is not set"))
        url = env.get("OLLAMA_URL")
        if url is not None:
            parts = urllib.parse.urlsplit(url)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                findings.append(_finding("high", "OLLAMA_URL", "must be an http(s) URL"))
            elif parts.scheme == "http" and parts.hostname not in ("127.0.0.1", "localhost", "::1"):
                findings.append(_finding("medium", "OLLAMA_URL", "prompts would travel unencrypted to another host"))
        return {"status": "ok", "sane": not any(f["severity"] in BLOCKING for f in findings), "findings": findings}
