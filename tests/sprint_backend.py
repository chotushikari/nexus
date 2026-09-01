from nexus_api.schemas.domain import (
    ApprovalDecisionRequest,
    EventType,
    MissionStatus,
    PolicyOutcome,
    StartMissionRequest,
)
from nexus_api.services.mission import mission_service
from nexus_api.services.policy import evaluate_policy
from nexus_api.services.storage import store


def setup_function():
    store.reset()
    store.seed_agents_from_roster()


def test_roster_seeds_twenty_agents():
    assert len(store.list_agents()) == 20
    assert {agent.tier.value for agent in store.list_agents()} == {1, 2, 3}


def test_policy_gateway_has_allow_deny_and_approval_outcomes():
    allowed = evaluate_policy("david-brooks", "financial_lookup", {"vendorId": "acme"})
    approval = evaluate_policy(
        "david-brooks",
        "create_payment",
        {"amount": 500000, "currency": "INR"},
    )
    denied = evaluate_policy("elena-rao", "bank-account.read", {})

    assert allowed.outcome == PolicyOutcome.allow
    assert approval.outcome == PolicyOutcome.require_approval
    assert denied.outcome == PolicyOutcome.deny


def test_acme_mission_pauses_for_human_approval_then_completes():
    mission_service.seed_demo()
    mission = mission_service.start_mission(
        StartMissionRequest(
            enterpriseId="wayne-enterprises",
            title="ACME Vendor Onboarding",
            objective="Evaluate ACME Technologies and onboard if compliant.",
            vendorId="acme-technologies",
        )
    )

    assert mission.status == MissionStatus.awaiting_approval
    assert mission.awaitingApprovalId is not None
    assert len(store.list_approvals()) == 1

    completed = mission_service.decide_approval(
        mission.awaitingApprovalId,
        ApprovalDecisionRequest(decision="granted", decidedBy="operator"),
    )

    assert completed.status == MissionStatus.completed
    event_types = [event.type for event in store.list_events(completed.id)]
    assert EventType.mission_created in event_types
    assert EventType.security_alert in event_types
    assert EventType.approval_requested in event_types
    assert EventType.approval_granted in event_types
    assert EventType.mission_completed in event_types

