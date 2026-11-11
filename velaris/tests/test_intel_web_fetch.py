"""The fetcher connects to the address it checked, not to the name. No network needed."""
import datetime
import http.server
import socketserver
import ssl
import threading

import httpx
import pytest

from velaris.intel import web_fetch
from velaris.intel.web_fetch import FetchError, Fetcher, check_public, pinned

PUBLIC, PUBLIC_2, PRIVATE = "93.184.216.34", "93.184.216.35", "10.0.0.5"


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


class Site:
    """A fake transport that records where each request was actually sent."""

    def __init__(self, routes=None, unreachable=()):
        self.seen, self.routes, self.unreachable = [], routes or {}, set(unreachable)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append({"connected_to": request.url.host, "host_header": request.headers["host"],
                          "sni": request.extensions.get("sni_hostname"), "path": request.url.path,
                          "cookie": request.headers.get("cookie")})
        if request.url.host in self.unreachable:
            raise httpx.ConnectError("no route to host", request=request)
        return self.routes.get((request.headers["host"], request.url.path)) or httpx.Response(
            200, headers={"content-type": "text/html", "set-cookie": "session=abc; Path=/"}, text="<p>hello</p>")


def answers(*replies):
    """A resolver that gives each reply in turn, then repeats the last one; .calls counts lookups."""
    def resolver(host):
        resolver.calls.append(host)
        return list(replies[min(len(resolver.calls), len(replies)) - 1])
    resolver.calls = []
    return resolver


def fetcher(site, resolver, **kw):
    return Fetcher(transport=httpx.MockTransport(site), resolver=resolver, min_gap_s=0, cache_ttl_s=0,
                   obey_robots=False, **kw)


def test_name_that_turns_private_after_the_check_is_never_connected_to():
    site, resolver = Site(), answers([PUBLIC], [PRIVATE])      # first answer public, second private
    with pytest.raises(FetchError) as refused:
        fetcher(site, resolver).fetch("https://rebind.test/page")
    assert refused.value.reason == "blocked_address"
    assert site.seen == []                                      # nothing was sent anywhere
    assert resolver.calls == ["rebind.test", "rebind.test"]     # the early gate, then the connect's own lookup


def test_connection_goes_to_the_address_that_was_checked():
    site, resolver = Site(), answers([PUBLIC], [PUBLIC_2])
    got = fetcher(site, resolver).fetch("https://site.test/page")
    # Each request does one lookup, checks it and connects to exactly that answer; the URL the
    # client is given holds the address, so there is no name left for the socket layer to resolve.
    assert site.seen == [{"connected_to": PUBLIC_2, "host_header": "site.test", "sni": "site.test",
                          "path": "/page", "cookie": None}]
    assert len(resolver.calls) == 2
    assert got.text == "<p>hello</p>" and got.final_url == "https://site.test/page"   # the name, not the address


def test_one_private_address_in_the_answer_blocks_the_whole_name():
    site = Site()
    with pytest.raises(FetchError) as refused:
        fetcher(site, answers([PUBLIC, PRIVATE])).fetch("https://mixed.test/")
    assert refused.value.reason == "blocked_address" and site.seen == []
    assert check_public("https://ok.test/", lambda host: [PUBLIC, PUBLIC_2, PUBLIC]) == [PUBLIC, PUBLIC_2]


def test_redirects_are_resolved_checked_and_pinned_hop_by_hop():
    hop = httpx.Response(302, headers={"location": "http://elsewhere.test:8080/landing"})
    inward = httpx.Response(302, headers={"location": "https://inside.test/admin"})
    site = Site({("site.test", "/hop"): hop, ("site.test", "/inward"): inward})

    def resolver(host):
        return {"site.test": [PUBLIC], "elsewhere.test": [PUBLIC_2], "inside.test": [PRIVATE]}[host]

    f = fetcher(site, resolver)
    got = f.fetch("https://site.test/hop")
    assert [(s["connected_to"], s["host_header"], s["sni"]) for s in site.seen] == [
        (PUBLIC, "site.test", "site.test"), (PUBLIC_2, "elsewhere.test:8080", None)]   # plain http: no TLS name
    assert got.final_url == "http://elsewhere.test:8080/landing"
    site.seen.clear()
    with pytest.raises(FetchError) as refused:
        f.fetch("https://site.test/inward")
    assert refused.value.reason == "blocked_address"
    assert [s["connected_to"] for s in site.seen] == [PUBLIC]   # the private hop was never contacted


def test_next_checked_address_is_tried_when_one_cannot_be_reached():
    site = Site(unreachable=["2606:2800:220:1::1"])
    got = fetcher(site, answers(["2606:2800:220:1::1", PUBLIC])).fetch("https://dual.test/")
    assert [s["connected_to"] for s in site.seen] == ["2606:2800:220:1::1", PUBLIC] and got.status == 200
    dead = Site(unreachable=[PUBLIC])
    with pytest.raises(FetchError) as failed:
        fetcher(dead, answers([PUBLIC])).fetch("https://down.test/")
    assert failed.value.reason == "network"


def test_cookies_do_not_travel_between_sites_on_one_address():
    site = Site()
    f = fetcher(site, answers([PUBLIC]))
    f.fetch("https://first.test/")          # answers with Set-Cookie
    f.fetch("https://second.test/")         # same address, different site
    f.fetch("https://first.test/again")
    assert [s["cookie"] for s in site.seen] == [None, None, None]


def test_robots_fetch_is_pinned_too():
    site = Site({("site.test", "/robots.txt"): httpx.Response(200, text="User-agent: *\nDisallow: /private")})
    f = Fetcher(transport=httpx.MockTransport(site), resolver=answers([PUBLIC]), min_gap_s=0, cache_ttl_s=0)
    assert f.fetch("https://site.test/page").status == 200
    assert [(s["connected_to"], s["path"]) for s in site.seen] == [(PUBLIC, "/robots.txt"), (PUBLIC, "/page")]
    with pytest.raises(FetchError) as refused:
        f.fetch("https://site.test/private/x")
    assert refused.value.reason == "robots_disallowed"


def test_pinned_request_shape():
    url, headers, extensions = pinned("https://user:pw@example.com:8443/a?b=1", PUBLIC)
    assert (str(url), headers, extensions) == (
        f"https://user:pw@{PUBLIC}:8443/a?b=1", {"Host": "example.com:8443"}, {"sni_hostname": "example.com"})
    url, headers, extensions = pinned("http://example.com/a", "2606:2800:220:1::1")
    assert (str(url), headers, extensions) == ("http://[2606:2800:220:1::1]/a", {"Host": "example.com"}, {})


def test_certificate_is_checked_against_the_name_not_the_address(tmp_path):
    """Against a real TLS server on loopback: pinning must not turn certificate checking into
    'whatever the address presents'. Uses httpx directly because the Fetcher refuses loopback."""
    pytest.importorskip("cryptography")
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "pinned.test")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("pinned.test")]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    cert_file, key_file = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    seen = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen["host"] = self.headers["Host"]
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    # TCPServer, not HTTPServer: the latter looks up its own host name on bind, which can take seconds
    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert_file, key_file)
    tls.sni_callback = lambda sock, server_name, ctx: seen.__setitem__("sni", server_name)
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        with httpx.Client(verify=ssl.create_default_context(cafile=str(cert_file)), trust_env=False) as client:
            url, headers, extensions = pinned(f"https://pinned.test:{port}/x", "127.0.0.1")
            assert client.get(url, headers=headers, extensions=extensions).text == "ok"
            assert seen == {"host": f"pinned.test:{port}", "sni": "pinned.test"}
            url, headers, extensions = pinned(f"https://other.test:{port}/x", "127.0.0.1")
            with pytest.raises(httpx.ConnectError, match="CERTIFICATE_VERIFY_FAILED"):
                client.get(url, headers=headers, extensions=extensions)   # same address, wrong name
    finally:
        server.shutdown()
        server.server_close()


def test_module_self_check_still_passes():
    web_fetch.demo()
