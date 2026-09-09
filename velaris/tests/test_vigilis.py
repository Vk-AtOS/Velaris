import sys
import os
import json
import pytest
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
from velaris.agents.VIGILIS.main import VigilisAgent

def test_health_check():
    agent = VigilisAgent()
    status = agent.health_check()
    assert status['agent'] == 'VIGILIS'
    assert status['status'] == 'ok'

def test_keypair_and_sign_verify():
    agent = VigilisAgent()
    priv, pub = agent.generate_test_keypair()
    assert priv is not None
    assert pub is not None
    message = b'hello vigilis'
    sig = agent.sign_message(message)
    assert isinstance(sig, (bytes, bytearray))
    ok = agent.verify_signature(message, sig)
    assert ok is True

def test_policy_evaluation_allows_by_default():
    agent = VigilisAgent()
    res = agent.evaluate_policy({})
    assert res['allowed'] is True
    assert isinstance(res['reasons'], list)