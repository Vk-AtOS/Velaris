"""Round 3 (KAN-89): LYRA live mode and run_loop, LONG_RUN_STABILITY_SIMULATOR input, MULTILINGUAL_BRAIN.translate."""
import builtins
import pytest

import velaris.agents.LYRA_VOICE_ENGINE.main as lyra
from velaris.agents.LONG_RUN_STABILITY_SIMULATOR.main import LongRunStabilitySimulator
from velaris.agents.MULTILINGUAL_BRAIN.main import MultilingualBrain


def live(monkeypatch, heard):
    """A live-mode engine whose microphone 'hears' the given transcripts in turn."""
    e = lyra.LyraVoiceEngine(lyra.LyraVoiceConfig(mode="live"))
    it = iter(heard)
    monkeypatch.setattr(e, "listen", lambda: b"x")
    monkeypatch.setattr(e, "transcribe", lambda audio: next(it, ""))
    monkeypatch.setattr(lyra.time, "sleep", lambda s: None)
    monkeypatch.setattr(e, "speak", lambda t: True)
    return e


def test_live_speech_without_the_wake_word_is_ignored_and_the_loop_ends_when_idle(monkeypatch):
    e = live(monkeypatch, ["order a pizza", "lyra check the server", "lyrical balance", ""])
    seen = []
    e.run_loop(handler=lambda r: seen.append(r) or {}, stop_after=0, max_idle=3)
    assert [r["routed_to"] for r in seen] == ["IT_INFRA_ENGINE"]          # one command; the others never reached the handler
    assert e._running is False


def test_live_run_loop_hands_the_handler_a_result_not_a_bare_intent_and_counts_commands(monkeypatch):
    e = live(monkeypatch, ["lyra grid balance", "lyra server", "lyra status"])
    seen = []
    e.run_loop(handler=lambda r: seen.append(r) or {}, stop_after=2)
    assert len(seen) == 2 and all(r["status"] == "ok" and "routed_to" in r for r in seen)


def test_cli_loop_stops_when_typed_input_ends(monkeypatch):
    e = lyra.LyraVoiceEngine(lyra.LyraVoiceConfig(mode="cli"))
    lines = iter(["check the server"])

    def fake_input(prompt=""):
        try:
            return next(lines)
        except StopIteration:
            raise EOFError from None
    monkeypatch.setattr(builtins, "input", fake_input)
    monkeypatch.setattr(e, "speak", lambda t: True)
    seen = []
    e.run_loop(handler=lambda r: seen.append(r) or {})                   # used to spin forever on EOF
    assert [r["routed_to"] for r in seen] == ["IT_INFRA_ENGINE"]


@pytest.mark.parametrize("bad", [[1, float("nan")], [1, float("inf")], [True, 2], ["1", "2"], None, "12", [1] * 100_001])
def test_stability_simulator_refuses_input_that_is_not_a_list_of_finite_numbers(bad):
    with pytest.raises(ValueError):
        LongRunStabilitySimulator().simulate(bad)


def test_stability_results_are_bounded():
    s = LongRunStabilitySimulator()
    for i in range(1100):
        s.simulate([0, 1])
    assert s.summary()["runs"] == 1000


def test_translate_keeps_punctuation_and_spacing_and_does_not_alias_the_mapping():
    m = MultilingualBrain()
    mapping = {"Hello": "namaste", "world": "duniya"}
    assert m.register_language("hi", mapping) is True
    mapping["world"] = "changed later"
    assert m.translate("hi", "Hello,  world! (HELLO)") == "namaste,  duniya! (namaste)"
    with pytest.raises(TypeError):
        m.translate("hi", None)
    with pytest.raises(ValueError):
        m.register_language("ta", {"a": 1})
