"""A real HTTP server on 127.0.0.1 that answers like an OpenAI-compatible provider, from a script.

    with FakeModelServer() as srv:
        srv.reply("/chat/completions", {...})          # JSON answer, status 200
        srv.reply("/chat/completions", status=500)     # error
        srv.base_url                                   # http://127.0.0.1:<port>/v1
    srv.requests                                       # [(method, path, headers, body)]
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeModelServer:
    def __init__(self) -> None:
        self.script, self.requests = {}, []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):          # keep test output quiet
                pass

            def _answer(self):
                n = int(self.headers.get("content-length") or 0)
                body = self.rfile.read(n).decode() if n else ""
                path = self.path.split("/v1", 1)[-1]
                outer.requests.append((self.command, path, dict(self.headers), json.loads(body) if body else None))
                queue = outer.script.get(path) or [{"status": 404, "json": {"error": "no script"}}]
                step = queue.pop(0) if len(queue) > 1 else queue[0]
                time.sleep(step.get("delay", 0))
                raw = step.get("raw")
                raw = raw if raw is not None else json.dumps(step.get("json", {})).encode()
                self.send_response(step.get("status", 200))
                self.send_header("content-type", step.get("content_type", "application/json"))
                self.send_header("content-length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            do_GET = do_POST = _answer

        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base_url = f"http://127.0.0.1:{self._srv.server_address[1]}/v1"

    def reply(self, path: str, json: object = None, *, status: int = 200, raw: bytes = None, delay: float = 0,
              content_type: str = "application/json") -> None:
        self.script.setdefault(path, []).append({"json": json, "status": status, "raw": raw, "delay": delay,
                                                 "content_type": content_type})

    def __enter__(self):
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._srv.shutdown()
        self._srv.server_close()


def chat_reply(text: str = "hi", tokens=(5, 7), tool_calls=None) -> dict:
    msg = {"role": "assistant", "content": text}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    out = {"choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls" if tool_calls else "stop"}]}
    if tokens:
        out["usage"] = {"prompt_tokens": tokens[0], "completion_tokens": tokens[1]}
    return out
