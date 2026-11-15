"""
Velaris Core Configuration
Phase 1 — Core Initialization
Provides project-root resolution and base configuration registry.
"""

from pathlib import Path

# Dynamically resolve project root relative to this file,
# instead of hard‑coding a machine‑specific absolute path.
PROJECT_ROOT = str(Path(__file__).resolve().parents[2])

def resolve_path(relative_path: str) -> str:
    """Resolve a path relative to the Velaris project root."""
    return str(Path(PROJECT_ROOT) / relative_path)

VELARIS_CONFIG = {
    "project_root": PROJECT_ROOT,
    "version": "0.1-phase1-bootstrap",
}
