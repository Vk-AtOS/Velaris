"""KAN-11: provider registry. CRUD, encrypted keys, rotation, redaction, fail-closed."""
import json
import logging

import pytest

from velaris.core import vault
from velaris.intel import llm, providers, trace
from velaris.intel.paths import data_dir

KEY = "sk-live-ABCDEFGH-1234567890"


def test_crud_and_the_key_is_never_returned():
    p = providers.create("work-gw", kind="openai_compatible", base_url="https://gw.example.com/v1/",
                         api_key=KEY, models=["m1"], sensitivity_allowed=["internal", "public"])
    assert p.base_url == "https://gw.example.com/v1" and p.key_last4 == KEY[-4:] and p.has_key
    assert p.sensitivity_allowed == ("public", "internal")
    shown = json.dumps([p.public(), [x.public() for x in providers.list_providers()]]) + repr(p)
    assert KEY not in shown and "ABCDEFGH" not in shown
    assert providers.credentials("work-gw") == KEY
    providers.update("work-gw", enabled=False, models=["m1", "m2"])
    assert not providers.get("work-gw").enabled and list(providers.get("work-gw").models) == ["m1", "m2"]
    assert providers.delete("work-gw") and providers.get("work-gw") is None and not providers.delete("work-gw")


def test_the_key_is_encrypted_on_disk_and_bound_to_its_provider():
    providers.create("a-gw", kind="openai_compatible", base_url="https://a.example.com/v1", api_key=KEY)
    raw = (data_dir() / "agents" / "llm_providers" / "providers.json").read_text()
    assert KEY not in raw and "ABCDEFGH" not in raw and "sealed_key" in raw
    doc = json.loads(raw)
    assert doc["schema_version"] == 1
    import base64
    blob = base64.b64decode(doc["providers"]["a-gw"]["sealed_key"])
    with pytest.raises(vault.VaultError):                       # moved to another provider's record: refused
        vault.open_bytes(blob, "provider-key:b-gw")


def test_rotation_replaces_the_key_and_keeps_the_rest():
    providers.create("rot", kind="openai_compatible", base_url="https://r.example.com/v1", api_key=KEY)
    p = providers.rotate("rot", "sk-second-KEY-0000-9999")
    assert providers.credentials("rot") == "sk-second-KEY-0000-9999" and p.key_last4 == "9999" and p.rotated_at > 0
    assert "ABCDEFGH" not in (data_dir() / "agents" / "llm_providers" / "providers.json").read_text()


def test_without_the_vault_key_nothing_is_stored(monkeypatch):
    monkeypatch.delenv("VELARIS_VAULT_KEY")
    monkeypatch.delenv("VELARIS_VAULT_KEY_FILE", raising=False)
    with pytest.raises(vault.VaultKeyError):
        providers.create("nokey", kind="openai_compatible", base_url="https://r.example.com/v1", api_key=KEY)
    assert providers.get("nokey") is None
    providers.create("local", kind="ollama")                    # no key to protect: fine
    assert providers.get("local").has_key is False


def test_refuses_bad_records():
    bad = [dict(kind="nope"), dict(kind="openai_compatible"),                       # unknown kind; no base_url
           dict(kind="openai_compatible", base_url="ftp://x"),
           dict(kind="openai_compatible", base_url="https://u:p@x.example.com/v1"),
           dict(kind="openai_compatible", base_url="https://x.example.com/v1", sensitivity_allowed=["secret"]),
           dict(kind="openai_compatible", base_url="https://x.example.com/v1", free_pool=True,
                sensitivity_allowed=["restricted"])]
    for kw in bad:
        with pytest.raises(providers.ProviderError):
            providers.create("p1", **kw)
    for pid in ("Bad Id", "", "anthropic", "ollama"):
        with pytest.raises(providers.ProviderError):
            providers.create(pid, kind="ollama")
    providers.create("dup", kind="ollama")
    with pytest.raises(providers.ProviderError):
        providers.create("dup", kind="ollama")


def test_default_sensitivity_is_public_only():
    assert providers.create("dflt", kind="ollama").sensitivity_allowed == ("public",)


def test_the_key_never_reaches_the_trace_or_the_logs(caplog):
    caplog.set_level(logging.DEBUG)
    providers.create("lg", kind="openai_compatible", base_url="http://127.0.0.1:1/v1", api_key=KEY, allow_local=True,
                     sensitivity_allowed=["public"])
    providers.rotate("lg", "sk-other-KEY-77777777")
    with pytest.raises(llm.LLMError) as e:                      # nothing listens on port 1
        llm.LLM().complete("hello", model="lg:m", sensitivity="public")
    assert KEY not in str(e.value)
    everything = (data_dir() / "trace.jsonl").read_text() + caplog.text + str(e.value)
    assert KEY not in everything and "sk-other-KEY-77777777" not in everything
    assert trace.verify()["ok"]
