"""
Velaris Core Loader
Phase 1 — Core Initialization
Provides safe import mechanisms and standardized module loading.
"""

import importlib
from .exceptions import ModuleLoadError
from .utils import log

def safe_import(module_path):
    try:
        log(f"Importing module: {module_path}")
        return importlib.import_module(module_path)
    except Exception as e:
        raise ModuleLoadError(f"Failed to import module '{module_path}': {e}") from e

def initialize_core():
    log("Velaris Core Initialization complete.")
    return True
