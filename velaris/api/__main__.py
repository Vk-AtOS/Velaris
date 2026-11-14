"""python3.11 -m velaris.api: serve the API on VELARIS_API_HOST:VELARIS_API_PORT (127.0.0.1:8730).

Refuses to start unless VELARIS_API_SECRET, VELARIS_IDENTITY_PUBLIC_KEY and VELARIS_ORG are set. One
process on purpose: the replay cache lives in memory (velaris/api/auth.py).
"""
import os

import uvicorn

from velaris.api.app import Settings, create_app
from velaris.api.observability import configure_logging, listener_address, serve_internal


def main() -> None:
    configure_logging()
    app = create_app(Settings.from_env())
    addr = listener_address()           # VELARIS_METRICS_PORT: unauthenticated /metrics on loopback, never published
    if addr:
        serve_internal(app.state.metrics, app.state.gauges, *addr)
    uvicorn.run(app, host=os.environ.get("VELARIS_API_HOST", "127.0.0.1"),
                port=int(os.environ.get("VELARIS_API_PORT", "8730")), workers=1, log_level="info", log_config=None)


if __name__ == "__main__":
    main()
