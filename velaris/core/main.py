"""
Velaris Core Entry Point
Phase 1 — Core Initialization
Provides the unified startup routine for the core system.
"""

from .config import PROJECT_ROOT
from .loader import initialize_core, safe_import
from .utils import log

def velaris_start():
    log("Starting Velaris Phase-1 Core...")

    initialize_core()

    log(f"Project root: {PROJECT_ROOT}")
    log("Core modules loaded successfully.")
    log("Velaris Core is now ready for Phase-2 restoration.")

    return True

if __name__ == "__main__":
    velaris_start()
