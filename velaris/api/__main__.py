"""python3.11 -m velaris.api: serve the API on VELARIS_API_HOST:VELARIS_API_PORT (127.0.0.1:8730).

Refuses to start unless VELARIS_API_SECRET, VELARIS_IDENTITY_PUBLIC_KEY and VELARIS_ORG are set. One
process on purpose: the replay cache lives in memory (velaris/api/auth.py).
"""
import os

import uvicorn

from velaris.api.app import Settings, create_app


def main() -> None:
    app = create_app(Settings.from_env())
    uvicorn.run(app, host=os.environ.get("VELARIS_API_HOST", "127.0.0.1"),
                port=int(os.environ.get("VELARIS_API_PORT", "8730")), workers=1, log_level="info")


if __name__ == "__main__":
    main()
