from nexus_api.schemas.domain import PolicyOutcome
from nexus_api.services.policy import evaluate_policy
from nexus_api.services.storage import store


def test_finance_read_is_allowed():
    store.reset()
    store.seed_agents_from_roster()

    decision = evaluate_policy("david-brooks", "financial_lookup", {"vendorId": "acme"})

    assert decision.outcome == PolicyOutcome.allow


def test_finance_payment_requires_approval_above_threshold():
    store.reset()
    store.seed_agents_from_roster()

    decision = evaluate_policy(
        "david-brooks",
        "create_payment",
        {"amount": 500000, "currency": "INR"},
    )

    assert decision.outcome == PolicyOutcome.require_approval


def test_unknown_tool_defaults_to_deny():
    store.reset()
    store.seed_agents_from_roster()

    decision = evaluate_policy("elena-rao", "bank-account.read", {})

    assert decision.outcome == PolicyOutcome.deny
    assert decision.reason == "identity_scope_violation"

