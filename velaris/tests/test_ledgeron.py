from decimal import Decimal
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
    assert bal == Decimal('69.50')        # exact paise (KAN-85): no float tolerance

def test_reconcile_and_find():
    a = LedgeronAgent()
    a.record_transaction('acctX', 'x1', 50)
    res = a.reconcile('acctX', 50)
    assert res['match'] is True
    txs = a.find_transactions('acctX', 'x1')
    assert len(txs) == 1


def test_a_repeated_transaction_id_is_not_counted_twice_and_money_is_exact():
    import pytest
    a = LedgeronAgent()
    first = a.record_transaction('acct', 'dup', 100)
    assert a.record_transaction('acct', 'dup', 100) is first and a.get_balance('acct') == Decimal('100.00')   # a retry
    with pytest.raises(ValueError):
        a.record_transaction('acct', 'dup', 90)                    # same id, different amount
    for bad in (float('nan'), float('inf'), True, '1.234', None, 'abc'):
        with pytest.raises(ValueError):
            a.record_transaction('acct', 'bad', bad)
    for i in range(10):
        a.record_transaction('acct2', f'p{i}', 0.1)
    assert a.get_balance('acct2') == Decimal('1.00') and a.reconcile('acct2', 1)['match'] is True    # 10 x 0.1 is exactly 1
    assert a.reconcile('acct2', 1.01)['match'] is False and a.reconcile('acct2', float('nan'))['match'] is False
