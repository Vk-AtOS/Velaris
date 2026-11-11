"""
Velaris Security Engine (Phase 2 Stub)
Validation and integrity checks are not implemented yet: both deny (fail closed).
"""
from velaris.core.utils import log

class SecurityEngine:

    def __init__(self):
        log('[SecurityEngine] Initialized')

    def validate(self, data):
        """Not implemented: denies (fail closed) until a real validation exists."""
        log(f'[SecurityEngine] VALIDATE denied, no real check implemented: {data}')
        return False

    def integrity_check(self, data):
        """Not implemented: denies (fail closed) until a real integrity check exists."""
        log(f'[SecurityEngine] INTEGRITY CHECK denied, no real check implemented: {data}')
        return False
security = SecurityEngine()