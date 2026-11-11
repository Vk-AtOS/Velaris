import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
import json
import subprocess
from typing import Dict, Any, Optional

logger = logging.getLogger("CALL_TRANSCRIBER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - CALL_TRANSCRIBER - %(levelname)s - %(message)s"))
logger.addHandler(handler)


class CallTranscriber:
    """
    Local speech-to-text transcription using OpenAI Whisper (runs entirely on-device).
    Requires: pip install openai-whisper  (or faster-whisper for speed)
    Model sizes: tiny/base/small/medium/large — default 'small' balances speed+accuracy.
    No audio is sent to any external API. Fully air-gapped capable.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.model_size = self.config.get("whisper_model", "small")
        self.language = self.config.get("language", "en")
        self._model = None  # lazy-loaded on first use
        self._use_faster = self.config.get("use_faster_whisper", False)

    def health_check(self) -> Dict[str, Any]:
        try:
            if self._use_faster:
                import faster_whisper  # noqa
            else:
                import whisper  # noqa
            available = True
        except ImportError:
            available = False
        return {
            "agent": "CALL_TRANSCRIBER",
            "status": "ok" if available else "degraded",
            "whisper_available": available,
            "model_size": self.model_size,
            "language": self.language,
            "backend": "faster-whisper" if self._use_faster else "openai-whisper",
        }

    def _load_model(self):
        if self._model is None:
            if self._use_faster:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                logger.info("faster-whisper model loaded: %s", self.model_size)
            else:
                import whisper
                self._model = whisper.load_model(self.model_size)
                logger.info("whisper model loaded: %s", self.model_size)

    def transcribe(self, filepath: str, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Transcribe a WAV/MP3/M4A file. Returns full text + segments with timestamps.
        filepath: absolute path to audio file
        language: override language (e.g. 'ta' for Tamil, 'en' for English)
        """
        if not os.path.exists(filepath):
            return {"error": f"file_not_found: {filepath}"}
        lang = language or self.language
        self._load_model()
        logger.info("Transcribing: %s lang=%s", filepath, lang)
        try:
            if self._use_faster:
                segments, info = self._model.transcribe(filepath, language=lang, beam_size=5)
                seg_list = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]
                full_text = " ".join(s["text"] for s in seg_list)
                return {
                    "filepath": filepath,
                    "language": info.language,
                    "language_probability": round(info.language_probability, 3),
                    "text": full_text,
                    "segments": seg_list,
                    "duration_sec": info.duration,
                }
            else:
                import whisper
                result = self._model.transcribe(filepath, language=lang, verbose=False)
                seg_list = [{"start": s["start"], "end": s["end"], "text": s["text"].strip()}
                            for s in result.get("segments", [])]
                return {
                    "filepath": filepath,
                    "language": result.get("language"),
                    "text": result["text"].strip(),
                    "segments": seg_list,
                }
        except Exception as e:
            logger.error("Transcription failed: %s", e)
            return {"error": str(e), "filepath": filepath}

    def transcribe_and_save(self, filepath: str, output_path: Optional[str] = None,
                             language: Optional[str] = None) -> Dict[str, Any]:
        """
        Transcribe and save result as JSON alongside the audio file.
        """
        result = self.transcribe(filepath, language)
        if "error" in result:
            return result
        if output_path is None:
            output_path = os.path.splitext(filepath)[0] + "_transcript.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        result["transcript_path"] = output_path
        logger.info("Transcript saved: %s", output_path)
        return result

    def transcribe_to_text(self, filepath: str, language: Optional[str] = None) -> str:
        """Convenience: returns just the text string."""
        result = self.transcribe(filepath, language)
        return result.get("text", result.get("error", ""))
