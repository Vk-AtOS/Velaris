import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
import subprocess
import json
import threading
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger("CALL_RECORDER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - CALL_RECORDER - %(levelname)s - %(message)s"))
logger.addHandler(handler)

_SESSIONS: Dict[str, Dict] = {}  # session_id → session state
_LOCK = threading.Lock()


class CallRecorder:
    """
    Local call/meeting audio recorder using system microphone.
    Uses ffmpeg (must be installed) to capture audio to WAV files.
    Output stored in config["recordings_dir"] (default: ./recordings/).
    No audio leaves the machine — fully local.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.recordings_dir = self.config.get("recordings_dir",
            os.path.join(os.path.dirname(__file__), "recordings"))
        os.makedirs(self.recordings_dir, exist_ok=True)
        self._ffmpeg = self.config.get("ffmpeg_path", "ffmpeg")
        # Input device: 'default' on Linux, ':0' on macOS (coreaudio), 'audio=...' on Windows
        self._input_device = self.config.get("input_device", "default")
        self._audio_backend = self.config.get("audio_backend", self._detect_backend())

    def _detect_backend(self) -> str:
        import platform
        p = platform.system()
        if p == "Darwin":
            return "avfoundation"
        if p == "Windows":
            return "dshow"
        return "alsa"

    def health_check(self) -> Dict[str, Any]:
        has_ffmpeg = subprocess.run(
            [self._ffmpeg, "-version"], capture_output=True
        ).returncode == 0
        return {
            "agent": "CALL_RECORDER",
            "status": "ok" if has_ffmpeg else "degraded",
            "ffmpeg_available": has_ffmpeg,
            "recordings_dir": self.recordings_dir,
            "backend": self._audio_backend,
        }

    def start(self, call_id: str, participants: list = None,
              meeting_title: str = "") -> Dict[str, Any]:
        """
        Start recording. Returns session info including file path.
        call_id: caller-provided stable identifier for this call/meeting.
        """
        session_id = str(uuid.uuid4())
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in meeting_title)[:40]
        filename = f"{ts}_{safe_title or call_id}.wav"
        filepath = os.path.join(self.recordings_dir, filename)

        # macOS: input ":0" = default mic via avfoundation
        if self._audio_backend == "avfoundation":
            device = self.config.get("input_device", ":0")
            cmd = [self._ffmpeg, "-y", "-f", "avfoundation", "-i", device,
                   "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", filepath]
        elif self._audio_backend == "dshow":
            device = self.config.get("input_device", "audio=Microphone")
            cmd = [self._ffmpeg, "-y", "-f", "dshow", "-i", device,
                   "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", filepath]
        else:  # alsa
            device = self.config.get("input_device", "default")
            cmd = [self._ffmpeg, "-y", "-f", "alsa", "-i", device,
                   "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", filepath]

        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        session = {
            "session_id": session_id,
            "call_id": call_id,
            "meeting_title": meeting_title,
            "participants": participants or [],
            "filepath": filepath,
            "started_at": datetime.now().isoformat(),
            "status": "recording",
            "_proc": proc,
        }
        with _LOCK:
            _SESSIONS[session_id] = session

        logger.info("Recording started: session=%s file=%s", session_id, filepath)
        return {k: v for k, v in session.items() if not k.startswith("_")}

    def stop(self, session_id: str) -> Dict[str, Any]:
        """Stop recording and return file path + duration info."""
        with _LOCK:
            session = _SESSIONS.get(session_id)
        if not session:
            return {"error": "session_not_found"}
        proc = session.get("_proc")
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
        stopped_at = datetime.now().isoformat()
        filepath = session["filepath"]
        size_bytes = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        # 16kHz mono 16-bit = 32000 bytes/sec
        duration_sec = size_bytes / 32000 if size_bytes > 0 else 0
        with _LOCK:
            session["status"] = "completed"
            session["stopped_at"] = stopped_at
            session["duration_sec"] = round(duration_sec, 1)
            session["size_bytes"] = size_bytes
        logger.info("Recording stopped: session=%s duration=%.1fs file=%s",
                    session_id, duration_sec, filepath)
        return {
            "session_id": session_id,
            "filepath": filepath,
            "duration_sec": round(duration_sec, 1),
            "size_bytes": size_bytes,
            "status": "completed",
        }

    def list_recordings(self) -> list:
        """List all WAV files in recordings dir with basic metadata."""
        recordings = []
        for f in sorted(os.listdir(self.recordings_dir)):
            if f.endswith(".wav"):
                fpath = os.path.join(self.recordings_dir, f)
                size = os.path.getsize(fpath)
                recordings.append({
                    "filename": f,
                    "path": fpath,
                    "size_bytes": size,
                    "duration_sec": round(size / 32000, 1),
                    "created": datetime.fromtimestamp(os.path.getctime(fpath)).isoformat(),
                })
        return recordings

    def get_session(self, session_id: str) -> Dict[str, Any]:
        with _LOCK:
            session = _SESSIONS.get(session_id, {})
        return {k: v for k, v in session.items() if not k.startswith("_")}
