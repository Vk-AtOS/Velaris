"""KAN-45: the eval runner is ready for a real model: the chain comes from the environment, only the key can be missing."""
import json
import subprocess
import sys
from pathlib import Path

from velaris.agentkit.harness_eval import model_chain, preflight
from velaris.agentkit.harness_spec import ROOT
from velaris.api.allowlist import rule_for  # noqa: F401  (import order: the allowlist loads the agents first)
from velaris.intel.tools import input_schema

RUNNER = Path(ROOT) / "tools" / "eval_runner.py"


def test_chain_from_argument_then_environment_then_offline():
    assert model_chain("anthropic:claude-sonnet-4-6, ollama:llama3.1:8b", {}) == ["anthropic:claude-sonnet-4-6", "ollama:llama3.1:8b"]
    assert model_chain(None, {"VELARIS_EVAL_MODELS": "bedrock:x"}) == ["bedrock:x"]
    assert model_chain("a:b", {"VELARIS_EVAL_MODELS": "bedrock:x"}) == ["a:b"] and model_chain(None, {}) == []


def test_preflight_names_the_missing_setting_and_never_a_value():
    assert preflight(["anthropic:m"], {}) == ["anthropic:m: set ANTHROPIC_API_KEY"]
    assert preflight(["anthropic:m"], {"ANTHROPIC_API_KEY": "k"}) == [] and preflight(["ollama:llama3.1:8b"], {}) == []
    assert preflight(["bedrock:m"], {}) == ["bedrock:m: set AWS_BEARER_TOKEN_BEDROCK"]
    assert "provider:model" in preflight(["nonsense"], {})[0]
    assert "not registered" in preflight(["nope:m"], {})[0]


def test_the_runner_stops_with_exit_2_and_scores_nothing_when_the_key_is_missing(tmp_path):
    env = {"PATH": "/usr/bin:/bin", "VELARIS_DATA": str(tmp_path), "HOME": str(tmp_path)}
    r = subprocess.run([sys.executable, str(RUNNER), "--model", "anthropic:claude-sonnet-4-6", "--out-dir", str(tmp_path / "o")],
                       capture_output=True, text=True, env=env, cwd=ROOT)
    assert r.returncode == 2 and "set ANTHROPIC_API_KEY" in r.stderr and not (tmp_path / "o").exists()


def test_eval_sample_arguments_have_the_type_the_tool_schema_asks_for():
    """A List[Dict] parameter used to be advertised as an object by a text-matching shortcut; the eval sets sampled {}."""
    from velaris.backend.engine import backend
    props = input_schema(backend.agent_class("POLARIS").rank_long_term)["properties"]
    assert props["strategies"]["type"] == "array"
    case = next(c for c in json.loads((Path(ROOT) / "evals/operations/POLARIS.json").read_text())["cases"] if c["id"] == "select-rank_long_term")
    assert isinstance(case["expect"]["calls"][0]["args"]["strategies"], list)
