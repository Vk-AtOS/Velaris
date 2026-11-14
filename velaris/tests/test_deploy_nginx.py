"""KAN-128: the nginx template allows exactly the public app's routes, with matching body caps, and masks tokens in logs."""
import re
from pathlib import Path

import pytest

from velaris.api.public import DEFAULT_LIMITS, create_public_app

NGINX = Path(__file__).resolve().parents[2] / "deploy" / "nginx"
CONF = (NGINX / "velaris-public.conf").read_text()
HTTP = (NGINX / "velaris-public-http.conf").read_text()
SNIPPET = (NGINX / "snippets" / "velaris-public-proxy.conf").read_text()
TOKEN = "T" * 30
LOCATIONS = re.findall(r"location ~ (\^\S+\$)\s*\{(.*?include snippets)", CONF)


def sample(path: str) -> str:
    return re.sub(r"\{(token)\}", TOKEN, re.sub(r"\{form_id\}", "form-1", path))


def allowed(path: str) -> bool:
    return any(re.fullmatch(rx, path) for rx, _ in LOCATIONS)


def test_every_app_route_is_allowed_and_nothing_else():
    routes = [r.path for r in create_public_app().routes if r.path.startswith(("/careers", "/schedule", "/interview", "/sign"))]
    assert len(routes) >= 17
    for path in routes:
        assert allowed(sample(path)), path
    for bad in ("/", "/health", "/metrics", "/docs", "/openapi.json", "/agents", "/careers/", "/careers/forms/",
                f"/sign/{TOKEN}/open/x", f"/sign/{TOKEN}/unknown", f"/careers/status/{TOKEN}/", "/careers/forms/a/b",
                f"/sign/short/open", f"/careers/forms/{'a' * 81}", "/careers/forms/a%2f..%2fb"):
        assert not allowed(bad), bad
    assert re.search(r"location / \{ return 404; \}", CONF)


def test_body_caps_match_the_app():
    def cap(rx_part):
        block = next(b for rx, b in LOCATIONS if rx_part in rx)
        m = re.search(r"client_max_body_size (\d+)([km])", block)
        return int(m.group(1)) * (1024 if m.group(2) == "k" else 1024 * 1024) if m else None
    assert cap("careers/apply") == DEFAULT_LIMITS["apply"].body
    assert cap("interview/[A-Za-z0-9_-]{20,100}/events") == DEFAULT_LIMITS["events"].body
    default = re.search(r"client_max_body_size (\d+)k;", CONF)
    assert int(default.group(1)) * 1024 >= max(v.body for k, v in DEFAULT_LIMITS.items() if k not in ("apply", "events"))


def test_methods_are_restricted_per_location():
    for rx, block in LOCATIONS:
        assert re.search(r"limit_except (GET|POST) \{ deny all; \}", block), rx


def test_headers_scrubbed_and_xff_replaced():
    assert "proxy_set_header X-Forwarded-For $remote_addr;" in SNIPPET and "proxy_add_x_forwarded_for" not in SNIPPET
    for h in ("Cookie", "Authorization", "X-Velaris-Signature", "X-Velaris-Identity"):
        assert re.search(rf'proxy_set_header {h} "";', SNIPPET), h
    assert "proxy_hide_header Set-Cookie;" in SNIPPET


def test_log_format_masks_tokens():
    fmt = re.search(r"log_format velaris_public (.*?);", HTTP, re.S).group(1)
    assert "$velaris_masked_uri" in fmt
    assert not re.search(r"\$(request\b|request_uri|args|query_string|http_referer|http_cookie|http_authorization)", fmt)
    mask = re.search(r"~\^\(\?<pre>(.*?)\)\[\^/\]\+\(\?<post>", HTTP).group(1)
    for prefix in ("careers/status", "careers/withdraw", "schedule", "interview", "sign"):
        assert prefix in mask
    assert re.match(mask, f"/sign/{TOKEN}/open").end() == len("/sign/")      # the prefix stops before the token

@pytest.mark.parametrize("env", ["VELARIS_PUBLIC_TRUST_PROXY", "VELARIS_PUBLIC_CORS_ORIGINS"])
def test_documented_env_exists_in_the_app(env):
    assert env in (Path(__file__).resolve().parents[1] / "api" / "public.py").read_text()
