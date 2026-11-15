import logging
import os
import time
import urllib.error
import urllib.request
import urllib.parse
import json
from typing import Dict, Any, Optional

logger = logging.getLogger("ZOHO_CONNECTOR")
DATA_CENTERS = ("com", "in", "eu", "com.au", "jp", "ca", "sa", "com.cn")
RETRY_STATUS = (429, 500, 502, 503, 504)
MAX_ATTEMPTS = 3


class ZohoError(RuntimeError):
    """A Zoho call that was refused (bad host, HTTP error, unusable reply). Never carries the access token."""

    def __init__(self, message: str, status: Optional[int] = None) -> None:
        super().__init__(message)
        self.status = status


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None       # a redirect would carry the Authorization header to whatever host answers: refuse to follow


_OPENER = urllib.request.build_opener(_NoRedirect)


class ZohoConnector:
    """
    OAuth2 base connector for all Zoho APIs.
    Handles token refresh automatically.
    Config keys: client_id, client_secret, refresh_token, dc (data center: com/in/eu)
    """
    TOKEN_URL = "https://accounts.zoho.{dc}/oauth/v2/token"

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.dc = self.config.get("dc", "in")  # India DC default for Knackforge
        self.client_id = self.config.get("client_id") or os.getenv("ZOHO_CLIENT_ID", "")
        self.client_secret = self.config.get("client_secret") or os.getenv("ZOHO_CLIENT_SECRET", "")
        self.refresh_token = self.config.get("refresh_token") or os.getenv("ZOHO_REFRESH_TOKEN", "")
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        self._extra_hosts = {h.lower() for h in self.config.get("allowed_hosts", []) if isinstance(h, str)}

    def health_check(self) -> Dict[str, Any]:
        configured = bool(self.client_id and self.client_secret and self.refresh_token)
        return {
            "agent": "ZOHO_CONNECTOR",
            "status": "ok" if configured else "unconfigured",
            "dc": self.dc,
            "configured": configured
        }

    def _check_url(self, url: str) -> None:
        """https only, and only the Zoho API hosts of the configured data centre (or config["allowed_hosts"]).

        The bearer token is attached to every request, so an arbitrary URL would hand it to that site."""
        parts = urllib.parse.urlsplit(url) if isinstance(url, str) else None
        host = (parts.hostname or "").lower() if parts else ""
        if self.dc not in DATA_CENTERS:
            raise ZohoError(f"unknown Zoho data centre {str(self.dc)[:20]!r}")
        ok = host in self._extra_hosts or host.endswith((f".zoho.{self.dc}", f".zohoapis.{self.dc}"))
        if not parts or parts.scheme != "https" or parts.username or parts.password or not ok:
            raise ZohoError("refused: the URL is not an https Zoho API host of the configured data centre")

    def _send(self, req: urllib.request.Request, timeout: float) -> Dict:
        """One call with a timeout, a bounded retry for 429 and 5xx, and errors that never include the token."""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                with _OPENER.open(req, timeout=timeout) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code in RETRY_STATUS and attempt < MAX_ATTEMPTS:
                    time.sleep(0.5 * attempt)
                    continue
                raise ZohoError(f"Zoho answered HTTP {e.code}", status=e.code) from None
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                if attempt < MAX_ATTEMPTS:
                    time.sleep(0.5 * attempt)
                    continue
                raise ZohoError(f"Zoho could not be reached: {type(e).__name__}") from None
            except ValueError:
                raise ZohoError("Zoho sent a reply that is not JSON") from None
        raise ZohoError("Zoho call failed")      # pragma: no cover - the loop always returns or raises

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        data = urllib.parse.urlencode({
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token"
        }).encode()

        url = self.TOKEN_URL.format(dc=self.dc)
        self._check_url(url)
        req = urllib.request.Request(url, data=data, method="POST")
        result = self._send(req, 15)
        if not isinstance(result.get("access_token"), str):
            raise ZohoError("Zoho did not return an access token")

        self._access_token = result["access_token"]
        self._token_expiry = time.time() + result.get("expires_in", 3600)
        logger.debug("Access token refreshed, expires in %s s", result.get("expires_in"))
        return self._access_token

    def get(self, url: str, params: Dict = None) -> Dict:
        self._check_url(url)                       # before the token is fetched or sent anywhere
        token = self._get_access_token()
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"Zoho-oauthtoken {token}"})
        return self._send(req, 30)

    def post(self, url: str, payload: Dict) -> Dict:
        self._check_url(url)
        token = self._get_access_token()
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={
                "Authorization": f"Zoho-oauthtoken {token}",
                "Content-Type": "application/json"
            }
        )
        return self._send(req, 30)
