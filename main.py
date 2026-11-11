import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from velaris.agents.inventory import format_inventory  # noqa: E402  (needs the path line above)
from velaris.backend.engine import backend  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Velaris entry point")
    parser.add_argument("--inventory", action="store_true",
                        help="print per-department counts of real / rule-based / not-implemented agents")
    args = parser.parse_args()
    if args.inventory:
        print(format_inventory())
        sys.exit(0)

    status = backend.status()
    print("=" * 50)
    print("VELARIS CORE V11 — ONLINE")
    print("=" * 50)
    print(f"Agents loaded : {status['agents_loaded']}")
    print(f"Agents failed : {len(status['agents_failed'])}")
    for name, error in status['agents_failed'].items():
        print(f"  ! {name}: {error}")
    print(f"Status        : {status['status']}")
    print("")
    print("First 10 agents:")
    for name in status['agent_list'][:10]:
        print(f"  - {name}")
    if status['agents_loaded'] > 10:
        print(f"  ... and {status['agents_loaded'] - 10} more")
    print("=" * 50)
