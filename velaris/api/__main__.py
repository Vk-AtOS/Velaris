"""python3.11 -m velaris.api: serve the API on VELARIS_API_HOST:VELARIS_API_PORT (127.0.0.1:8730).

Refuses to start unless VELARIS_API_SECRET, VELARIS_IDENTITY_PUBLIC_KEY and VELARIS_ORG are set.

VELARIS_API_WORKERS (default 1): the replay cache, public rate counters, state files and background jobs are safe
across worker processes (velaris.core.shared, filelock). The chat event queues (/chat/events) are still in each
process's memory, so keep 1 worker while chat clients use them, or put sticky routing in front.
"""
import os

import uvicorn

from velaris.api.app import Settings, create_app


def build():
    return create_app(Settings.from_env())


def main() -> None:
    Settings.from_env()          # fail at start-up, not in a worker, when the configuration is incomplete
    uvicorn.run("velaris.api.__main__:build", factory=True, host=os.environ.get("VELARIS_API_HOST", "127.0.0.1"),
                port=int(os.environ.get("VELARIS_API_PORT", "8730")), workers=max(1, int(os.environ.get("VELARIS_API_WORKERS", "1"))),
                log_level="info")


if __name__ == "__main__":
    main()
