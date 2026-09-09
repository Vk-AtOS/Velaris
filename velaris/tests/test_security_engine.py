"""
Velaris Security Engine Test Harness
Phase 2 — Module Restoration
Verifies validation and integrity-check behavior.
"""

from velaris.security.secure import security

def run_test():
    results = {}

    results["validate_result"] = security.validate("sample_input")
    results["integrity_result"] = security.integrity_check("sample_input")

    return results

if __name__ == "__main__":
    print(run_test())
