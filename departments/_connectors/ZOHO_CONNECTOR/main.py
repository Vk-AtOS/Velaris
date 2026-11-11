import logging
import os
import time
import urllib.request
import urllib.parse
import json
from typing import Dict, Any, Optional

logger = logging.getLogger("ZOHO_CONNECTOR")


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

    def health_check(self) -> Dict[str, Any]:
        configured = bool(self.client_id and self.client_secret and self.refresh_token)
        return {
            "agent": "ZOHO_CONNECTOR",
            "status": "ok" if configured else "unconfigured",
            "dc": self.dc,
            "configured": configured
        }

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
        req = urllib.request.Request(url, data=data, method="POST")

        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())

        self._access_token = result["access_token"]
        self._token_expiry = time.time() + result.get("expires_in", 3600)
        logger.debug("Access token refreshed, expires in %s s", result.get("expires_in"))
        return self._access_token

    def get(self, url: str, params: Dict = None) -> Dict:
        token = self._get_access_token()
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"Zoho-oauthtoken {token}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    def post(self, url: str, payload: Dict) -> Dict:
        token = self._get_access_token()
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={
                "Authorization": f"Zoho-oauthtoken {token}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
