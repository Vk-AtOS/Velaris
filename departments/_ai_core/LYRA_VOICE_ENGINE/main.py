# ================================================================================

"""Lyra voice engine: turns a spoken or typed command into a keyword-routed, simulated request and speaks the result.

LyraVoiceConfig.mode picks the input: "mock" (fixed fake transcript), "cli" (typed text) or anything else (microphone
via sounddevice, with whisper transcription when asr_backend is "whisper", else a typed fallback). Methods: listen()
(audio bytes or None), transcribe(audio), speak(text) (pyttsx3 or print; False only for empty text),
interpret_intent(text) (keyword match on infra/balance/status/simulate, otherwise "customer"; returns request_id, domain,
payload), run_once(user_text) and run_loop(handler, stop_after, max_idle). run_once only names the engine it would route to and
returns a simulated {"status": "ok", ...}; it calls no other agent. In live (microphone) mode a transcript is acted on
only when it starts with the wake word (default "lyra"; the word is removed first); other speech is ignored, and with
no wake word configured (None) everything is acted on. run_loop hands the handler the same result dict in every mode,
counts a handled command (not an ignored one) toward stop_after, stops by itself after `max_idle` (default 120)
consecutive empty or ignored turns or when typed input ends (EOF), and stop() ends it from another thread. A handler
exception in run_loop becomes a failed reply.
Keeps no state. Missing audio packages are logged and the affected step returns None or an empty string.
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable
import hashlib
import logging
import os
import tempfile
import time
import wave

logger = logging.getLogger("LYRA_VOICE_ENGINE")

# Optional audio packages. Without them the engine still runs in "mock" and "cli" modes;
# listen() / transcribe() / speak() say so in the log and return their empty result.
try:
    import sounddevice as sd
except (ImportError, OSError) as e:      # OSError: the package is there but the PortAudio library is not
    logger.info("sounddevice not available, microphone capture is off: %s", e)
    sd = None

try:
    import pyttsx3
except ImportError as e:
    logger.info("pyttsx3 not available, speech output falls back to print: %s", e)
    pyttsx3 = None

try:
    import whisper
except ImportError as e:
    logger.info("whisper not available, speech recognition is off: %s", e)
    whisper = None

@dataclass
class LyraVoiceConfig:
    mode: str = "mock"
    wake_word: Optional[str] = "lyra"
    tts_voice: Optional[str] = None
    asr_backend: Optional[str] = None
    sample_rate: int = 16000
    recording_seconds: float = 5.0

class LyraVoiceEngine:
    def __init__(self, cfg: Optional[LyraVoiceConfig] = None):
        self.cfg = cfg or LyraVoiceConfig()
        self._engine = None
        self._asr_model = None
        self._running = False
        if pyttsx3 is not None:
            try:
                self._engine = pyttsx3.init()
                if self.cfg.tts_voice:
                    try:
                        self._engine.setProperty("voice", self.cfg.tts_voice)
                    except Exception as e:
                        logger.warning("Voice %r could not be selected, using the default: %s",
                                       self.cfg.tts_voice, e)
            except Exception as e:
                logger.warning("Text-to-speech engine failed to start, falling back to print: %s", e)
                self._engine = None
        if self.cfg.asr_backend == "whisper" and whisper is not None:
            try:
                self._asr_model = whisper.load_model("small")
            except Exception as e:
                logger.warning("Whisper model failed to load, speech recognition is off: %s", e)
                self._asr_model = None

    def _hash(self, s: str) -> int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12], 16)

    def listen(self) -> Optional[bytes]:
        if self.cfg.mode in ("mock", "cli"):
            return None
        if sd is None:
            return None
        seconds = max(0.5, float(self.cfg.recording_seconds))
        try:
            samples = int(seconds * self.cfg.sample_rate)
            audio = sd.rec(frames=samples, samplerate=self.cfg.sample_rate, channels=1, dtype='int16')
            sd.wait()
            return audio.tobytes()
        except Exception as e:
            logger.warning("Microphone capture failed: %s", e)
            return None

    def transcribe(self, audio_bytes: Optional[bytes]) -> str:
        if self.cfg.mode == "mock":
            h = self._hash(self.cfg.wake_word or "lyra") % 1000
            return f"mock command {h}"
        if self.cfg.mode == "cli":
            return ""
        if audio_bytes is None:
            return ""
        if self._asr_model is not None:
            fd, wav_path = tempfile.mkstemp(suffix=".wav")      # owner-only; removed below in every case
            os.close(fd)
            try:
                with wave.open(wav_path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(self.cfg.sample_rate)
                    wf.writeframes(audio_bytes)
                result = self._asr_model.transcribe(wav_path)
                return result.get("text","").strip()
            except Exception as e:
                logger.warning("Transcription failed: %s", e)
                return ""
            finally:
                try:
                    os.unlink(wav_path)
                except OSError as e:
                    logger.warning("Could not remove temporary recording %s: %s", wav_path, e)
        return ""

    def speak(self, text: str) -> bool:
        if not text:
            return False
        final_text = f"{text}"
        if self._engine is not None:
            try:
                self._engine.say(final_text)
                self._engine.runAndWait()
                return True
            except Exception as e:
                logger.warning("Speech output failed, printing instead: %s", e)
        print("[LYRA SPEAK]:", final_text)
        return True

    def interpret_intent(self, text: str) -> Dict[str,Any]:
        text_lower = (text or "").lower()
        if "infra" in text_lower or "server" in text_lower or "vm" in text_lower:
            domain = "it_infra"
            payload = {"action":"health_check","target":"all"}
        elif "balance" in text_lower or "grid" in text_lower:
            domain = "grid"
            payload = {"action":"assess","target":"local"}
        elif "status" in text_lower or "health" in text_lower:
            domain = "itsm"
            payload = {"action":"ticket_status","id":"TBD"}
        elif "simulate" in text_lower or "portfolio" in text_lower:
            domain = "portfolio"
            payload = {"action":"simulate_sample"}
        else:
            domain = "customer"
            payload = {"action":"greet"}
        rid = f"lyra-{self._hash(text or '') % 100000:05d}"
        return {"request_id": rid, "domain": domain, "payload": payload}

    def _wake(self, text: str) -> Optional[str]:
        """The command after the wake word, or None when live speech did not start with it."""
        word = (self.cfg.wake_word or "").strip().lower()
        if not word:
            return text
        low = text.strip().lower()
        if low == word or low.startswith(word) and not low[len(word)].isalnum():
            return text.strip()[len(word):].lstrip(" ,.:;!-")
        return None

    def stop(self) -> None:
        self._running = False

    def _result(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        engine_name = {"it_infra": "IT_INFRA_ENGINE", "grid": "GRID_BALANCE_ENGINE", "itsm": "ITSM_ENGINE",
                       "portfolio": "PORTFOLIO_SIM_ENGINE", "customer": "CUSTOMER_BEHAVIOR_ENGINE"}.get(intent["domain"], "MAE")
        return {"status": "ok", "request_id": intent["request_id"], "routed_to": engine_name,
                "payload": intent["payload"], "message": f"Simulated execution for domain {intent['domain']}"}

    def run_once(self, user_text: Optional[str]=None) -> Dict[str,Any]:
        if self.cfg.mode in ("mock",):
            transcribed = self.transcribe(None)
        elif self.cfg.mode == "cli":
            if user_text is None:
                try:
                    user_text = input("Lyra (type your command)> ")
                except EOFError:          # no terminal attached: treat as an empty command
                    user_text = ""
            transcribed = user_text.strip()
        else:
            audio = self.listen()
            transcribed = self.transcribe(audio)
            if not transcribed:
                try:
                    user_text = input("Could not transcribe. Type command> ")
                    transcribed = user_text.strip()
                except EOFError:          # no terminal attached: nothing was said
                    transcribed = ""
            else:                          # spoken: only what follows the wake word counts
                heard = self._wake(transcribed)
                if heard is None:
                    return {"status": "ignored", "reason": "no wake word"}
                transcribed = heard
        intent = self.interpret_intent(transcribed)
        simulated_result = self._result(intent)
        spoken = f"Executed {simulated_result['routed_to']}. Result status {simulated_result['status']}."
        self.speak(spoken)
        return simulated_result

    def run_loop(self, handler: Optional[Callable[[Dict[str,Any]], Dict[str,Any]]] = None, stop_after: int = 0,
                 max_idle: int = 120):
        self._running = True
        iterations = idle = 0
        try:
            while self._running:
                if self.cfg.mode == "mock":
                    res = self.run_once()
                elif self.cfg.mode == "cli":
                    try:
                        line = input("Lyra (type your command)> ")
                    except EOFError:               # typed input ended: there will never be another command
                        break
                    res = self.run_once(line)
                else:
                    audio = self.listen()
                    text = self.transcribe(audio)
                    heard = self._wake(text) if text else None
                    if heard is None:              # silence or speech without the wake word
                        idle += 1
                        if idle >= max_idle:
                            break
                        time.sleep(0.5)
                        continue
                    res = self._result(self.interpret_intent(heard))
                idle = 0
                reply = {}
                if handler:
                    try:
                        reply = handler(res)
                    except Exception as e:
                        reply = {"status":"failed","error":str(e)}
                if isinstance(reply, dict) and "speak" in reply:
                    self.speak(str(reply["speak"]))
                else:
                    self.speak("Command processed.")
                iterations += 1
                if stop_after > 0 and iterations >= stop_after:
                    break
        finally:
            self._running = False

if __name__ == "__main__":
    cfg = LyraVoiceConfig(mode="cli", asr_backend=None)
    lyra = LyraVoiceEngine(cfg)
    print("Lyra Voice Engine (CLI mode). Type 'exit' to quit.")
    while True:
        try:
            res = lyra.run_once()
            print("=>", res)
            cmd = input("Continue? (y/n)> ").strip().lower()
            if cmd not in ("y","yes"):
                break
        except KeyboardInterrupt:
            break

# ================================================================================