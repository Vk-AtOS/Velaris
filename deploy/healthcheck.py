"""Container health probe: healthcheck.py PORT [PATH]. With PATH: GET must answer 200. Without: the port must accept a connection."""
import socket
import sys
import urllib.request


def main(argv):
    port = int(argv[1])
    if len(argv) > 2:
        return 0 if urllib.request.urlopen(f"http://127.0.0.1:{port}{argv[2]}", timeout=3).status == 200 else 1
    socket.create_connection(("127.0.0.1", port), timeout=3).close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (OSError, ValueError):
        sys.exit(1)
