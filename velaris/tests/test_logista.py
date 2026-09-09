import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.LOGISTA.main import LogistaAgent

def test_health():
    l = LogistaAgent()
    h = l.health_check()
    assert h['agent'] == 'LOGISTA'
    assert h['status'] == 'ok'

def test_allocation():
    l = LogistaAgent()
    resources = {'r1': 10, 'r2': 5}
    demand = {'r1': 7, 'r2': 10}
    alloc = l.allocate_resources(resources, demand)
    assert alloc['r1'] == 7
    assert alloc['r2'] == 5

def test_route_selection():
    l = LogistaAgent()
    routes = {'A': 5.0, 'B': 3.2, 'C': 7.1}
    best = l.choose_route(routes)
    assert best == 'B'