"""
Velaris Core Exceptions
Phase 1 — Core Initialization
Defines standardized exception classes for consistent error handling.
"""

class VelarisError(Exception):
    """Base class for all Velaris-related exceptions."""
    pass

class ConfigError(VelarisError):
    """Configuration problems within the core system."""
    pass

class IntegrityError(VelarisError):
    """Raised when checksum or file integrity validation fails."""
    pass

class ModuleLoadError(VelarisError):
    """Raised when a critical Velaris module fails to load."""
    pass
