# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable
import hashlib
import json
import queue
import threading
import time

try:
    import sounddevice as sd
except Exception:
    sd = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    import whisper
except Exception:
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
                    except Exception:
                        pass
            except Exception:
                self._engine = None
        if self.cfg.asr_backend == "whisper" and whisper is not None:
            try:
                self._asr_model = whisper.load_model("small")
            except Exception:
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
        except Exception:
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
            try:
                import numpy as np
                arr = np.frombuffer(audio_bytes, dtype='int16').astype('float32') / 32768.0
                import tempfile, wave, os
                tf = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                with wave.open(tf.name, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(self.cfg.sample_rate)
                    wf.writeframes(audio_bytes)
                result = self._asr_model.transcribe(tf.name)
                try:
                    os.unlink(tf.name)
                except Exception:
                    pass
                return result.get("text","").strip()
            except Exception:
                return ""
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
            except Exception:
                pass
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
        rid = f"lyra-{self._hash(text) % 100000:05d}"
        return {"request_id": rid, "domain": domain, "payload": payload}

    def run_once(self, user_text: Optional[str]=None) -> Dict[str,Any]:
        if self.cfg.mode in ("mock",):
            transcribed = self.transcribe(None)
        elif self.cfg.mode == "cli":
            if user_text is None:
                try:
                    user_text = input("Lyra (type your command)> ")
                except Exception:
                    user_text = ""
            transcribed = user_text.strip()
        else:
            audio = self.listen()
            transcribed = self.transcribe(audio)
            if not transcribed:
                try:
                    user_text = input("Could not transcribe. Type command> ")
                    transcribed = user_text.strip()
                except Exception:
                    transcribed = ""
        intent = self.interpret_intent(transcribed)
        engine_name = {
            "it_infra":"IT_INFRA_ENGINE",
            "grid":"GRID_BALANCE_ENGINE",
            "itsm":"ITSM_ENGINE",
            "portfolio":"PORTFOLIO_SIM_ENGINE",
            "customer":"CUSTOMER_BEHAVIOR_ENGINE"
        }.get(intent["domain"], "MAE")
        simulated_result = {
            "status":"ok",
            "request_id": intent["request_id"],
            "routed_to": engine_name,
            "payload": intent["payload"],
            "message": f"Simulated execution for domain {intent['domain']}"
        }
        spoken = f"Executed {simulated_result['routed_to']}. Result status {simulated_result['status']}."
        self.speak(spoken)
        return simulated_result

    def run_loop(self, handler: Optional[Callable[[Dict[str,Any]], Dict[str,Any]]] = None, stop_after: int = 0):
        self._running = True
        iterations = 0
        try:
            while self._running:
                if self.cfg.mode == "mock":
                    res = self.run_once()
                elif self.cfg.mode == "cli":
                    res = self.run_once()
                else:
                    audio = self.listen()
                    text = self.transcribe(audio)
                    if not text:
                        time.sleep(0.5)
                        continue
                    res = self.interpret_intent(text)
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