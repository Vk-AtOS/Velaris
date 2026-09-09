"""
Velaris Memory Mesh — Phase 2 Bootstrap
Provides basic shared in-process memory for Velaris subsystems.
"""
from velaris.core.utils import log

class MemoryMesh:

    def __init__(self):
        self.store = {}

    def set(self, key, value):
        log(f'[MemoryMesh] SET {key} = {value}')
        self.store[key] = value

    def get(self, key, default=None):
        value = self.store.get(key, default)
        log(f'[MemoryMesh] GET {key} -> {value}')
        return value

    def delete(self, key):
        if key in self.store:
            log(f'[MemoryMesh] DELETE {key}')
            del self.store[key]
        else:
            log(f'[MemoryMesh] DELETE Key Not Found: {key}')
mesh = MemoryMesh()