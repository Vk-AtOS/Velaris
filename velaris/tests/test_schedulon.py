import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.SCHEDULON.main import SchedulonAgent

def test_health():
    s = SchedulonAgent()
    h = s.health_check()
    assert h['agent'] == 'SCHEDULON'
    assert h['status'] == 'ok'

def test_load_distribution():
    s = SchedulonAgent()
    tasks = [5, 3, 4, 2]
    result = s.distribute_load(tasks, workers=2)
    assert len(result) == 2
    assert sum(result[0]) + sum(result[1]) == sum(tasks)

def test_next_available_slot():
    s = SchedulonAgent()
    schedule = {'w1': 10, 'w2': 4, 'w3': 7}
    best = s.next_available_slot(schedule)
    assert best == 'w2'