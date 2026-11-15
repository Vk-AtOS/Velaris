# Atlassian connectors: per-user OAuth (KAN-73)

Two ways to authenticate the JIRA and CONFLUENCE connectors:

1. **Service account** (default): one API token and e-mail for the whole deployment. Reads are limited to the
   `jira_projects` / `confluence_spaces` allow-lists, writes are approved steps. Everybody sees what that account can see.
2. **Per user** (`VELARIS_ATLASSIAN_AUTH=oauth`, or `config["auth"] = "oauth"`): each person connects their own Atlassian account with
   OAuth 2.0 (3LO). Calls run with that person's access token, so Atlassian applies that person's own permissions; a person who cannot
   see a project gets Atlassian's own "not found/forbidden". There is no fallback to the shared account: a person who has not connected
   gets `user_not_connected`, one whose grant was revoked gets `reauthorize_required`. The allow-lists still apply on top.

## What the owner provides (one-time)
1. At developer.atlassian.com create an **OAuth 2.0 (3LO)** app. Permissions: Jira `read:jira-work`, `write:jira-work`; Confluence
   `read:confluence-content.all`, `read:confluence-space.summary`; `offline_access` (needed for refresh tokens).
2. Callback URL: the AetherOS route that forwards the browser to Velaris `GET /integrations/atlassian/callback` as the signed-in person
   (AetherOS side: a page that passes `code` and `state` through; not part of this repository change).
3. Set `ATLASSIAN_OAUTH_CLIENT_ID`, `ATLASSIAN_OAUTH_CLIENT_SECRET`, `VELARIS_ATLASSIAN_REDIRECT_URI` (https), and `VELARIS_ATLASSIAN_AUTH=oauth`
   from the secret manager. Nothing is stored in code or in the data directory in clear: tokens are encrypted with the vault key.

## Flow
`POST /integrations/atlassian/connect` returns the consent URL (state: signed, single use, bound to the person and organisation, 10 min).
The person approves in Atlassian; AetherOS calls `GET /integrations/atlassian/callback?code=&state=` as that person; Velaris exchanges the
code, finds the site and stores the tokens. `GET /integrations/atlassian/status` shows whether the person is connected;
`DELETE /integrations/atlassian` disconnects. Access tokens (1 h) are refreshed 90 s before expiry; Atlassian rotates the refresh token
on every refresh and the new one is stored. A refresh that Atlassian rejects (grant revoked, password changed, 90 days idle) deletes the
local tokens and asks the person to reconnect.

## Offboarding
`POST /integrations/atlassian/revoke {"user_id": ...}` (role `hr_admin` or `governance_admin`) deletes a person's tokens;
`OAuth.revoke_user(org, user_id)` is the same call for the HR offboarding flow to make. Also remove the grant in the person's Atlassian
account or the organisation's Atlassian admin console (apps with access) so the refresh token dies at Atlassian too.

## Not verified here
No real Atlassian site or OAuth app was available: the token endpoint, accessible-resources and `api.atlassian.com/ex/{jira|confluence}/{cloudId}`
URL shapes follow Atlassian's published documentation and are tested against a mock (`velaris/tests/test_atlassian_oauth.py`). The first
real login should be checked against the live responses.
