"""Call transcriber: local speech-to-text of audio files with OpenAI Whisper or faster-whisper.
CallTranscriber.transcribe(filepath, language=None) returns {"filepath", "language", "text",
"segments"[, "language_probability", "duration_sec"]} where segments carry start, end and text.
transcribe_and_save(filepath, output_path=None, language=None) also writes the result as JSON
(default <audio>_transcript.json) and adds "transcript_path"; the output must be a .json path, not a
symlink, next to the audio file or under this agent's data folder (agent_dir). transcribe_to_text
returns just the text (or the error string). health_check() reports whether the Whisper package imports
(status "ok" or "degraded"). The model is loaded lazily on first use; no audio leaves the machine.
State: no persistent state apart from the transcript files it is asked to write.
Failure: a missing file returns {"error": "file_not_found: ..."}; any transcription error, including
the Whisper package not being installed, returns {"error": ...} instead of raising; a rejected output
path returns {"error": <reason>}.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
import json
from typing import Dict, Any, Optional

from velaris.core.access import check_caller
from velaris.intel.paths import agent_dir, agent_file

logger = logging.getLogger("CALL_TRANSCRIBER")


AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"})


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
        if self._model is not None:
            return
        package = "faster-whisper" if self._use_faster else "openai-whisper"
        try:        # optional packages: neither is in requirements.txt
            if self._use_faster:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            else:
                import whisper
                self._model = whisper.load_model(self.model_size)
        except ImportError as e:
            raise RuntimeError(f"transcription needs the '{package}' package, which is not installed "
                               f"(pip install {package})") from e
        logger.info("%s model loaded: %s", package, self.model_size)

    def transcribe(self, filepath: str, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Transcribe a WAV/MP3/M4A file. Returns full text + segments with timestamps.
        filepath: absolute path to audio file
        language: override language (e.g. 'ta' for Tamil, 'en' for English)
        """
        _, refused = check_caller("CALL_TRANSCRIBER", "transcribe", {"file": os.path.basename(str(filepath))[:80]})
        if refused:
            return {"error": refused["status"], "reason": refused["reason"], "filepath": str(filepath)[:200]}
        problem = self._audio_problem(filepath)
        if problem:
            return {"error": problem, "filepath": str(filepath)[:200]}
        lang = language or self.language
        try:
            self._load_model()
            logger.info("Transcribing: %s lang=%s", filepath, lang)
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

    def _audio_roots(self):
        extra = [r for r in self.config.get("audio_roots", []) if isinstance(r, str)]
        return [os.path.realpath(r) for r in [str(agent_dir("CALL_TRANSCRIBER")), agent_file("CALL_RECORDER", "recordings"), *extra]]

    def _audio_problem(self, filepath: str) -> Optional[str]:
        """Only an audio file under a recordings folder (this agent's, CALL_RECORDER's, or config["audio_roots"]) is read:
        an unrestricted path would transcribe, and so disclose, any file the process can read."""
        if not isinstance(filepath, str) or "\x00" in filepath or os.path.splitext(filepath)[1].lower() not in AUDIO_EXTENSIONS:
            return f"filepath must be an audio file ({', '.join(sorted(AUDIO_EXTENSIONS))})"
        real = os.path.realpath(filepath)
        if not any(real.startswith(r + os.sep) for r in self._audio_roots()):
            return "filepath is outside the folders this agent may read audio from"
        if not os.path.isfile(real):
            return f"file_not_found: {os.path.basename(filepath)}"
        return None

    @staticmethod
    def _output_problem(filepath: str, output_path: str) -> Optional[str]:
        """A transcript is a .json file next to the audio or under this agent's data folder; nowhere else."""
        if not isinstance(output_path, str) or not output_path.endswith(".json") or "\x00" in output_path:
            return "output_path must be a .json file path"
        target = os.path.realpath(output_path)
        if os.path.islink(output_path):
            return "output_path may not be a symbolic link"
        roots = [os.path.realpath(os.path.dirname(os.path.abspath(filepath))), os.path.realpath(str(agent_dir("CALL_TRANSCRIBER")))]
        if not any(os.path.dirname(target) == r or target.startswith(r + os.sep) for r in roots):
            return "output_path must be next to the audio file or under the transcriber's data folder"
        return None

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
        problem = self._output_problem(filepath, output_path)
        if problem:
            return {"error": problem, "filepath": filepath}
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        result["transcript_path"] = output_path
        logger.info("Transcript saved: %s", output_path)
        return result

    def transcribe_to_text(self, filepath: str, language: Optional[str] = None) -> str:
        """Convenience: returns just the text string. Raises RuntimeError on failure: an error message is not a transcript."""
        result = self.transcribe(filepath, language)
        if "error" in result:
            raise RuntimeError(str(result["error"]))
        return result["text"]
