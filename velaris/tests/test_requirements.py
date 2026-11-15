"""requirements.txt lists exactly the third-party packages the code imports unconditionally.

An import inside `try: ... except ImportError` is optional: the code must cope without it,
so it is not required here. Anything else that is not standard library must be listed, and
nothing may be listed that no file imports.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL = {"velaris", "agents", "live", "departments", "main", "conftest"}
IMPORT_NAME = {"python-pptx": "pptx", "python-docx": "docx", "pyyaml": "yaml", "beautifulsoup4": "bs4",
               "openai-whisper": "whisper", "faster-whisper": "faster_whisper"}


def _catches_import_error(node: ast.Try) -> bool:
    for handler in node.handlers:
        types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
        if any(getattr(t, "id", None) in ("ImportError", "ModuleNotFoundError") for t in types):
            return True
    return False


def imports(root: Path = ROOT):
    """({module: [files]} imported unconditionally, {module: [files]} imported optionally)."""
    required, optional = {}, {}
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        guarded = {id(x) for t in ast.walk(tree) if isinstance(t, ast.Try) and _catches_import_error(t)
                   for b in t.body for x in ast.walk(b)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module.split(".")[0]]
            else:
                continue
            for m in modules:
                if m not in sys.stdlib_module_names and m not in LOCAL:
                    (optional if id(node) in guarded else required).setdefault(m, []).append(str(rel))
    return required, optional


def listed(root: Path = ROOT):
    names = set()
    for line in (root / "requirements.txt").read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            name = re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0].lower()
            names.add(IMPORT_NAME.get(name, name.replace("-", "_")))
    return names


def test_every_unconditional_third_party_import_is_listed():
    required, _ = imports()
    missing = {m: files[:3] for m, files in required.items() if m.lower() not in listed()}
    assert not missing, f"imported but not in requirements.txt (list it, or guard the import): {missing}"


def test_nothing_is_listed_that_is_not_imported():
    required, optional = imports()
    unused = listed() - {m.lower() for m in list(required) + list(optional)}
    assert not unused, f"in requirements.txt but never imported: {sorted(unused)}"


def test_transcriber_without_whisper_says_what_to_install(tmp_path, monkeypatch):
    from velaris.agents.CALL_TRANSCRIBER.main import CallTranscriber
    monkeypatch.setitem(sys.modules, "whisper", None)       # makes `import whisper` raise ImportError
    audio = tmp_path / "call.wav"
    audio.write_bytes(b"RIFF")
    from velaris.core.access import Caller, acting_as
    with acting_as(Caller("u", "kf")):
        out = CallTranscriber({"audio_roots": [str(tmp_path)]}).transcribe(str(audio))
    assert "openai-whisper" in out["error"] and "not installed" in out["error"]


def test_whatsapp_send_uses_httpx_and_does_not_call_a_refusal_sent(tmp_path, monkeypatch):
    import asyncio
    import functools

    import httpx

    from velaris.agents.WHATSAPP_BRIEFING import main as wa
    seen = []

    def handler(request):
        seen.append((str(request.url), request.headers["authorization"]))
        return httpx.Response(401 if "bad" in request.headers["authorization"] else 200, json={})

    monkeypatch.setattr(wa.httpx, "AsyncClient",
                        functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(handler)))
    config = {"db_path": str(tmp_path / "b.db"), "whatsapp_phone_id": "42", "whatsapp_to": "+911234"}
    ok = asyncio.run(wa.WhatsAppBriefingSystem({**config, "whatsapp_token": "good"}).send("hi"))
    refused = asyncio.run(wa.WhatsAppBriefingSystem({**config, "whatsapp_token": "bad"}).send("hi"))
    assert ok == {"status": "sent", "http_status": 200}
    assert refused["status"] == "error" and refused["http_status"] == 401
    assert seen[0] == ("https://graph.facebook.com/v17.0/42/messages", "Bearer good")
