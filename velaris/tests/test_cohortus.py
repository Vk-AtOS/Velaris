import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.COHORTUS.main import CohortusAgent

def test_health():
    c = CohortusAgent()
    h = c.health_check()
    assert h['agent'] == 'COHORTUS'
    assert h['status'] == 'ok'

def test_role_assignment():
    c = CohortusAgent()
    members = ['A', 'B', 'C']
    roles = ['leader', 'support']
    assigned = c.assign_roles(members, roles)
    assert assigned['A'] == 'leader'
    assert assigned['B'] == 'support'
    assert assigned['C'] == 'leader'

def test_clusters():
    c = CohortusAgent()
    clusters = c.collaboration_clusters(['a', 'b', 'c', 'd', 'e'], 2)
    assert clusters[0] == ['a', 'b']
    assert clusters[1] == ['c', 'd']
    assert clusters[2] == ['e']