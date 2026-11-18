"""KAN-120: the public app gives every response an X-Request-Id in the API's format and puts it in the log lines of that request."""
import re

from fastapi.testclient import TestClient

from velaris.api.public import PublicSettings, create_public_app


def test_public_app_sets_and_honours_request_id(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    c = TestClient(create_public_app(PublicSettings()), raise_server_exceptions=False)
    r = c.get("/nowhere")
    assert re.fullmatch(r"[0-9a-f]{16}", r.headers["x-request-id"])
    assert c.get("/nowhere", headers={"X-Trace-Id": "trace-from-aetheros1"}).headers["x-request-id"] == "trace-from-aetheros1"
    assert c.get("/nowhere", headers={"X-Request-Id": "bad id!"}).headers["x-request-id"] != "bad id!"     # unsafe shape: fresh id
