import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.LEDGERON.main import LedgeronAgent

def test_health():
    a = LedgeronAgent()
    h = a.health_check()
    assert h['agent'] == 'LEDGERON'
    assert h['status'] == 'ok'

def test_record_and_balance():
    a = LedgeronAgent()
    a.record_transaction('acct1', 't1', 100.0)
    a.record_transaction('acct1', 't2', -30.5)
    bal = a.get_balance('acct1')
    assert abs(bal - 69.5) < 1e-09

def test_reconcile_and_find():
    a = LedgeronAgent()
    a.record_transaction('acctX', 'x1', 50)
    res = a.reconcile('acctX', 50)
    assert res['match'] is True
    txs = a.find_transactions('acctX', 'x1')
    assert len(txs) == 1