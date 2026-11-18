#!/usr/bin/env python3.11
"""Run the mail connector against a real test mailbox, end to end (KAN-71), and print a report.

  export VELARIS_TEST_ADDRESS=velaris-test@yourdomain.example
  export VELARIS_TEST_SMTP_HOST=smtp.yourdomain.example VELARIS_TEST_SMTP_PORT=587 VELARIS_TEST_SMTP_SECURITY=starttls
  export VELARIS_TEST_SMTP_USER=... VELARIS_TEST_SMTP_PASS=...          # an app password; never your own
  export VELARIS_TEST_IMAP_HOST=imap.yourdomain.example VELARIS_TEST_IMAP_USER=... VELARIS_TEST_IMAP_PASS=...
  # optional, for the domain check: set a TXT record  _velaris.<domain>  to a token, then
  export VELARIS_TEST_DNS_DOMAIN=yourdomain.example VELARIS_TEST_DNS_TOKEN=<token>
  python3.11 tools/mail_e2e.py

Steps (velaris/tests/test_mail_live.py): send through the relay and read it back over IMAP; a message to a non-existent user of the
same domain and the DSN that comes back (parsed by velaris.mail.dsn); undo-send inside the window and a normal send afterwards; the
real DNS resolver reads the TXT record. The credentials stay in the environment: the script writes none of them anywhere, and the
mailbox must be a throw-away one (the tests send 3 to 5 messages). Exit 0 = every step passed, 1 = a failure (read the output),
2 = no credentials configured (nothing was run).
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEEDED = ["VELARIS_TEST_ADDRESS", "VELARIS_TEST_SMTP_HOST", "VELARIS_TEST_SMTP_USER", "VELARIS_TEST_SMTP_PASS",
          "VELARIS_TEST_IMAP_HOST", "VELARIS_TEST_IMAP_USER", "VELARIS_TEST_IMAP_PASS"]


def main() -> int:
    missing = [k for k in NEEDED if not os.environ.get(k)]
    if missing:
        print("not configured, nothing was run. Missing: " + ", ".join(missing))
        return 2
    return subprocess.call([sys.executable, "-m", "pytest", "-q", "-rA", "velaris/tests/test_mail_live.py", "-p", "no:cacheprovider"], cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
