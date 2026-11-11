"""
Velaris Core Utilities
Phase 1 — Core Initialization
Provides hashing, file checks, and minimal logging utilities.
"""

import hashlib
import os
from datetime import datetime

def sha256_of_file(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except FileNotFoundError:
        return None

def file_exists(path):
    return os.path.isfile(path)

def log(message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Velaris-CORE {now}] {message}")


def not_implemented(component, reason="no real implementation exists yet"):
    """
    Explicit result for logic that has no real implementation.
    Returned instead of a fabricated number so nothing made-up reaches a caller.
    """
    return {"status": "not_implemented", "score": None, "component": component, "reason": reason}
