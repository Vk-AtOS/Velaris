"""What offboarding must do to connected accounts (KAN-73).

revoke_connector_tokens(org, user_id, by) forgets the leaver's Atlassian OAuth tokens (velaris.core.atlassian_oauth.OAuth.revoke_user:
traced, idempotent). It raises on a store failure: the caller must NOT finish the exit with the tokens still usable, and may retry.
"""
from __future__ import annotations

from velaris.core.atlassian_oauth import OAuth


def revoke_connector_tokens(org: str, user_id: str, by: str) -> dict:
    oa = OAuth()
    try:
        return {"atlassian": oa.revoke_user(org, user_id, by=by)}
    finally:
        oa._http.close()
