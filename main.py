import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from velaris.backend.engine import backend

if __name__ == "__main__":
    status = backend.status()
    print("=" * 50)
    print("VELARIS CORE V11 — ONLINE")
    print("=" * 50)
    print(f"Agents loaded : {status['agents_loaded']}")
    print(f"Status        : {status['status']}")
    print("")
    print("First 10 agents:")
    for name in status['agent_list'][:10]:
        print(f"  - {name}")
    if status['agents_loaded'] > 10:
        print(f"  ... and {status['agents_loaded'] - 10} more")
    print("=" * 50)
