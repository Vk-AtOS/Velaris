"""VEL-81: with no model configured the gateway fails with a configuration error that names the settings.
Ollama is used only when it is named (OLLAMA_MODEL or VELARIS_MODEL=ollama:...), never as a silent localhost default.
No test here opens a connection: httpx.post is replaced by one that fails the test if it is reached."""
import httpx
import pytest

from velaris.intel import llm
from velaris.intel.errors import LLMError

CLEAR = ("VELARIS_MODEL", "ANTHROPIC_API_KEY", "AWS_BEARER_TOKEN_BEDROCK", "OLLAMA_MODEL", "OLLAMA_URL")
TOOLS = [{"type": "function", "function": {"name": "look", "parameters": {"type": "object"}}}]


@pytest.fixture
def bare(monkeypatch):
    for k in CLEAR:
        monkeypatch.delenv(k, raising=False)

    def no_network(*args, **kwargs):
        raise AssertionError("a model call reached the network")

    monkeypatch.setattr(httpx, "post", no_network)
    return monkeypatch


def test_nothing_configured_is_a_configuration_error_that_names_the_settings(bare):
    with pytest.raises(LLMError) as e:
        llm.default_model()
    for name in ("VELARIS_MODEL", "ANTHROPIC_API_KEY", "OLLAMA_MODEL"):
        assert name in str(e.value)


def test_a_model_call_with_nothing_configured_fails_before_any_request(bare):
    with pytest.raises(LLMError, match="VELARIS_MODEL"):
        llm.LLM().complete("hello")
    with pytest.raises(LLMError, match="VELARIS_MODEL"):
        llm.LLM().chat([{"role": "user", "content": "hi"}])


def test_ollama_needs_an_explicit_model(bare):
    bare.setenv("OLLAMA_MODEL", "llama3.1:8b")
    assert llm.default_model() == "ollama:llama3.1:8b"


def test_an_explicit_ollama_call_uses_the_configured_url(bare):
    bare.setenv("OLLAMA_MODEL", "llama3.1:8b")
    bare.setattr(llm, "OLLAMA_URL", "http://ollama.internal:11434")
    seen = []

    def fake_post(url, headers, body):
        seen.append(url)
        return {"response": "ok", "prompt_eval_count": 1, "eval_count": 1}

    bare.setattr(llm, "_post", fake_post)
    assert llm.LLM().complete("hi").text == "ok"
    assert seen == ["http://ollama.internal:11434/api/generate"]


def test_an_anthropic_key_selects_anthropic(bare):
    bare.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    assert llm.default_model().startswith("anthropic:")


def test_velaris_model_wins_over_the_others(bare):
    bare.setenv("OLLAMA_MODEL", "llama3.1:8b")
    bare.setenv("VELARIS_MODEL", "anthropic:claude-sonnet-4-6")
    assert llm.default_model() == "anthropic:claude-sonnet-4-6"


def test_tool_calls_on_a_non_openai_provider_name_the_setting(bare):
    bare.setenv("OLLAMA_MODEL", "llama3.1:8b")
    with pytest.raises(LLMError, match="VELARIS_MODEL"):
        llm.LLM().chat([{"role": "user", "content": "hi"}], tools=TOOLS)
