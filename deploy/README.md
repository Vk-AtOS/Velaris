# Deploying Velaris

One deployment serves one organisation (`VELARIS_ORG`). Two processes share one `VELARIS_DATA` directory:

| process | command | port | who may reach it |
|---|---|---|---|
| API | `python -m velaris.api` | 8730 | the AetherOS gateway only; never published |
| public app | `python -m velaris.api.public` | 8731 | the internet, through nginx (`deploy/nginx`) |

Both run **one worker**. The gateway replay cache (`velaris/api/auth.py`) and the public rate counters live in process memory, so a
second worker would let a replayed signed request or a burst through the sibling. Do not add `--workers`; run one deployment per
organisation. Raise capacity only after those two stores move to a shared store.

## Environment

| variable | process | meaning |
|---|---|---|
| `VELARIS_ORG` | both | the organisation this deployment belongs to (required) |
| `VELARIS_API_SECRET` | API | HMAC secret shared with the gateway, at least 32 bytes (required) |
| `VELARIS_IDENTITY_PUBLIC_KEY` | API | path of the AetherOS Ed25519 public key (PEM); mount read-only (required) |
| `VELARIS_DATA` | both | data directory (volume, mode 0700, owned by the service user) |
| `VELARIS_API_HOST` / `VELARIS_API_PORT` | API | bind address (default 127.0.0.1:8730; `0.0.0.0` only inside a container whose port is not published) |
| `VELARIS_PUBLIC_HOST` / `VELARIS_PUBLIC_PORT` | public | default 127.0.0.1:8731 |
| `VELARIS_PUBLIC_TRUST_PROXY` | public | `1` when exactly one trusted proxy (nginx) sets `X-Forwarded-For`: client IP = its last entry |
| `VELARIS_PUBLIC_CORS_ORIGINS` | public | comma-separated exact origins; unset = no CORS headers; `*` is refused |
| `VELARIS_METRICS_PORT` / `VELARIS_METRICS_HOST` | API | internal unauthenticated `/metrics` listener (default host 127.0.0.1). Never publish it |
| `VELARIS_LOG_JSON` / `VELARIS_LOG_LEVEL` | both | `0` gives plain text; level default INFO |
| `VELARIS_PRIME_URL`, `VELARIS_PRIME_API_KEY`, `VELARIS_MODEL`, ... | API | Prime approvals and the model gateway: see `velaris/core/prime.py`, `velaris/intel/llm.py` |

Secrets (`VELARIS_API_SECRET`, Prime key, any encryption key for personal-data stores) are supplied by the environment or a secret
manager; none is in an image or a manifest. Keys for encrypted stores must live **outside** `VELARIS_DATA`.

## Packaging

* **Docker**: `docker build -f deploy/Dockerfile -t velaris:local .` (python 3.11-slim, user uid 10001, `/data` volume, healthcheck).
  Run with `--read-only --tmpfs /tmp`; the image writes only to `/data` and `/tmp`. Dependencies install with
  `-c deploy/constraints.txt`, which pins the runtime closure to the versions the test suite ran against (regenerate it on a machine
  with network access when upgrading; CI runs `pip-audit` on it).
* **Compose**: `deploy/docker-compose.example.yml` (API on an internal network, public app bound to 127.0.0.1:8731).
* **systemd** (VPS): `deploy/systemd/*.service` and the two `*.env.example` files. Install under `/opt/velaris`, create user
  `velaris`, `install -m 600` the env files into `/etc/velaris/`, then `systemctl enable --now velaris-api velaris-public`.
* **Kubernetes**: `deploy/k8s/velaris.yaml` (PVC, two Deployments, ClusterIP Services, NetworkPolicies: the API accepts only the
  AetherOS gateway pods and Prometheus). Create the Secrets from `deploy/k8s/secret.example.yaml`'s shape; never apply that file.
  Replace every `CHANGE_ME`. The data PVC is ReadWriteOnce, so both pods are co-scheduled on one node.
* **CI**: `.github/workflows/ci.yml` (pytest, smoke, ruff, pip-audit, gitleaks). Gitleaks needs a `GITLEAKS_LICENSE` secret for
  organisation-owned repositories. ruff blocks only on real errors (`E9,F63,F7,F82`); the repository has about 180 style findings.
* **Smoke**: `python3.11 deploy/smoke.py` starts the API with a temp data dir and dummy credentials, then checks `/health`, that
  unsigned and wrongly signed requests get 401 and a correctly signed one succeeds.

Not verified here (no network or container runtime in the build environment): `docker build`, `kubectl apply`, `nginx -t`,
`systemd-analyze verify`. Run them once before the first rollout.

## Public app behind nginx (KAN-128)

Copy `deploy/nginx/velaris-public-http.conf` into `http {}`, `velaris-public.conf` into `conf.d/`, and
`snippets/velaris-public-proxy.conf` into `/etc/nginx/snippets/`; edit server names and certificates; `nginx -t`.

* Path allowlist: one `location ~` per route of `velaris/api/public.py`, tokens and form ids matched by their exact character class
  and length, one method each; `location / { return 404; }` for everything else (`/metrics`, `/agents`, docs). A test
  (`velaris/tests/test_deploy_nginx.py`) derives the routes from the app, so adding a public route without adding it here fails CI.
* Body caps equal the app's own (`DEFAULT_LIMITS`): 2 MiB for `careers/apply`, 64 KiB for interview events, 8 KiB elsewhere.
* Header scrubbing: `Cookie`, `Authorization`, `X-Velaris-*`, `X-Real-IP`, `X-Forwarded-Host` are blanked; `Set-Cookie`/`Server` hidden.
* `X-Forwarded-For` is **replaced** with the peer address (`$remote_addr`), never appended, and the app runs with
  `VELARIS_PUBLIC_TRUST_PROXY=1` so the client cannot pick its own rate-limit bucket. If another proxy or load balancer sits in
  front of nginx, add `set_real_ip_from <its address>; real_ip_header X-Forwarded-For;` (see the http file) so `$remote_addr` is the
  real client.
* Logs: tokens are in URL paths, so the access log writes `$velaris_masked_uri` (`/sign/***/open`) and never `$request`,
  `$request_uri`, `$args`, referer or cookies. The app's own logs mask any 24+ character token-like string.
* CORS: set `VELARIS_PUBLIC_CORS_ORIGINS` to the exact careers and sign origins; nginx adds no CORS headers.

## Observability (KAN-120)

* `GET /metrics` on the API: signed like every call and requires the `ops` or `governance_admin` role. Prometheus cannot sign, so
  scrape the internal listener instead: set `VELARIS_METRICS_PORT=9730` (loopback by default; in containers bind 0.0.0.0 on the
  internal network and keep the port out of any Service/ports list).
* Series: `velaris_calls_total{action,outcome}`, `velaris_refusals_total`, `velaris_approvals_requested_total`,
  `velaris_approvals_waiting` (gauge, from the flow store), `velaris_trace_failures_total`, `velaris_queue_depth` (requests in
  flight), `velaris_http_responses_total{status}`, `velaris_llm_{calls,failures,prompt_chars,output_chars,seconds}_total{model}`.
  There is no price table in the model gateway, so spend is characters and seconds per model; convert to money in Prometheus.
  Counters reset on restart (use `rate()`/`increase()`).
* Logs are JSON lines on stderr with `request_id` (taken from a valid `X-Request-Id`, else generated; also returned as a response
  header). The public app logs JSON with masked tokens too, but has no request id middleware.

## Backup and restore (KAN-117)

```
python3.11 deploy/backup/velaris_backup.py backup  --data /var/lib/velaris --out /var/backups/velaris [--lock-file FILE]
python3.11 deploy/backup/velaris_backup.py restore --archive /var/backups/velaris/velaris-data-<UTC>.tar.gz --target /var/lib/velaris [--force]
```

**Backup order.** SQLite files are copied with the online backup API; every other file is copied and accepted only if it did not
change while it was read. For all stores to agree with each other, do one of: (a) stop both services for the few seconds the
snapshot takes (`systemctl stop velaris-public velaris-api`, back up, start), the simplest and strictly consistent; or (b) pass
`--lock-file` pointing at the cross-process lock the stores take for writing (the file locks of the storage hardening work,
KAN-ticket for D4) so writers wait during the snapshot. Without either, each file is consistent but two stores may differ by a few
seconds of writes. Restore verifies the `.sha256` sidecar and every manifest hash, refuses unsafe archive members, and moves an
existing target aside (`<target>.pre-restore-<epoch>`) only with `--force`. Stop the services before restoring.

**Off-site, encrypted.** The archive is plaintext; encrypt before it leaves the host, with a key kept off the host:

```
age -r "$AGE_RECIPIENT" -o velaris-data-X.tar.gz.age velaris-data-X.tar.gz      # or: gpg --encrypt --recipient KEYID ...
rclone copyto velaris-data-X.tar.gz.age remote:velaris-backups/velaris-data-X.tar.gz.age   # or: aws s3 cp ... --sse
sha256sum velaris-data-X.tar.gz > velaris-data-X.tar.gz.sha256                   # kept next to the .age file; restore needs it
```

Back up separately and securely the data-encryption key for personal-data stores (it is outside `VELARIS_DATA` and therefore not in
the archive; an archive without it is unreadable by design) and the AetherOS public key / API secret from your secret manager.
**Restore drill** (quarterly): decrypt, `restore --target /tmp/drill`, start the API against it with `VELARIS_DATA=/tmp/drill`, run
`python3.11 deploy/smoke.py`-style checks and `GET /trace/verify`. `velaris/tests/test_deploy_backup.py` runs the same drill on temp dirs.
