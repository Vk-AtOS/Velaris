"""
Velaris Router Test Harness
Phase 2 — Module Restoration
Validates basic publish/subscribe behavior and logging integration.
"""

from velaris.agents.agents.router import router

TEST_RESULTS = []

def test_callback(msg):
    TEST_RESULTS.append(msg)

def run_test():
    router.subscribe("test_channel", test_callback)
    router.publish("test_channel", "hello_velaris")
    return TEST_RESULTS

if __name__ == "__main__":
    print(run_test())
