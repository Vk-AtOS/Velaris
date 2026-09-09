import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.CODEX.main import CodexAgent

def test_health():
    c = CodexAgent()
    s = c.health_check()
    assert s['agent'] == 'CODEX'
    assert s['status'] == 'ok'

def test_rule_storage_and_compare():
    c = CodexAgent()
    rules_v1 = {'allow': ['read', 'write'], 'deny': ['delete']}
    rules_v2 = {'allow': ['read', 'write'], 'deny': ['delete', 'export']}
    h1 = c.store_rules('system', rules_v1)
    assert h1 is not None
    assert c.rules_changed('system', rules_v1) is False
    assert c.rules_changed('system', rules_v2) is True