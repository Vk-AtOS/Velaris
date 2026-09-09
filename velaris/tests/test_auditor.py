import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.AUDITOR.main import AuditorAgent

def test_health():
    a = AuditorAgent()
    h = a.health_check()
    assert h['agent'] == 'AUDITOR'
    assert h['status'] == 'ok'

def test_compliance_checks():
    a = AuditorAgent()
    steps = ['load', 'scan', 'execute']
    required = ['load', 'execute']
    assert a.check_compliance(steps, required) is True
    assert a.check_compliance(steps, ['load', 'finish']) is False

def test_violation_detection():
    a = AuditorAgent()
    logs = ['ok', 'warning: overload', 'error detected']
    banned = ['warning', 'error']
    v = a.find_violations(logs, banned)
    assert len(v) == 2