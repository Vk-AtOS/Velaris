"""Loader discovers agents from departments/, and former allow-all security stubs deny."""
from velaris.agents.router import AgentRouter
from velaris.agents.CREDIT_RISK_ENGINE.main import BorrowerProfile, CreditRiskEngine
from velaris.agents.VIGILIS.main import VigilisAgent
from velaris.agents.ZERO_TRUST_PIPELINE.main import ZERO_TRUST_PIPELINEAgent
from velaris.agents.inventory import STATUSES, inventory
from velaris.security.secure import security


def test_loader_finds_agents():
    router = AgentRouter()
    assert router.count() > 0
    assert router.failed == {}
    # underscore-prefixed departments must be scanned too
    assert "ORCHESTRIX" in router.list_agents()      # _ai_core
    assert "ZOHO_CONNECTOR" in router.list_agents()  # _connectors


def test_former_allow_all_security_stubs_deny():
    assert ZERO_TRUST_PIPELINEAgent().verify("any-token") is False
    assert security.validate("anything") is False
    assert security.integrity_check("anything") is False


def test_forged_fallback_signature_is_rejected():
    agent = VigilisAgent()
    agent.generate_test_keypair()
    message = b"hello vigilis"
    assert agent.verify_signature(message, b"SIG:" + message[::-1][:32]) is False


def test_hash_scorer_returns_explicit_not_implemented():
    borrower = BorrowerProfile("br-001", 800000, 200000, 12, 1, 500000, "personal")
    result = CreditRiskEngine().compute_risk(borrower)
    assert result["status"] == "not_implemented"
    assert result["score"] is None
    assert "risk_score" not in result


def test_inventory_counts_every_agent_once():
    counted = sum(len(names) for dept in inventory().values() for names in dept.values())
    assert counted == AgentRouter().count()
    assert "CREDIT_RISK_ENGINE" in inventory()["finance"]["not_implemented"]
    assert set(inventory()["finance"]) == set(STATUSES)
