"""python3.11 -m velaris.api: serve the API on VELARIS_API_HOST:VELARIS_API_PORT (127.0.0.1:8730).

Refuses to start unless VELARIS_API_SECRET, VELARIS_IDENTITY_PUBLIC_KEY and VELARIS_ORG are set.

VELARIS_API_WORKERS (default 1): the replay cache, public rate counters, state files and background jobs are safe
across worker processes (velaris.core.shared, filelock). The chat event queues (/chat/events) are still in each
process's memory, so keep 1 worker while chat clients use them, or put sticky routing in front.
"""
import os

import uvicorn

from velaris.api.app import Settings, create_app
from velaris.api.observability import configure_logging, listener_address, serve_internal


def _workers() -> int:
    return max(1, int(os.environ.get("VELARIS_API_WORKERS", "1")))


def build():
    app = create_app(Settings.from_env())
    addr = listener_address()           # VELARIS_METRICS_PORT: unauthenticated /metrics on loopback, never published
    if addr and _workers() == 1:        # one listener port cannot be shared by several workers; use the signed GET /metrics then
        serve_internal(app.state.metrics, app.state.gauges, *addr)
    return app


def main() -> None:
    configure_logging()
    Settings.from_env()          # fail at start-up, not in a worker, when the configuration is incomplete
    uvicorn.run("velaris.api.__main__:build", factory=True, host=os.environ.get("VELARIS_API_HOST", "127.0.0.1"),
                port=int(os.environ.get("VELARIS_API_PORT", "8730")), workers=_workers(), log_level="info", log_config=None)


if __name__ == "__main__":
    main()
