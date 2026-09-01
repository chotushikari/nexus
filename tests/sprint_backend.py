"""Service-layer smoke suite (historically "sprint 1").

SANDBOX NOTE: authored where pytest/pydantic were unavailable, so this file was
NOT executed at authoring time. See tests/conftest.py.

This file was previously byte-identical to `tests/sprint1_backend.py`; the
duplicate has been removed and this is the one that is kept. It was also written
against the old synchronous, hard-coded implementation and asserted the retired
`wayne-enterprises` / `acme-technologies` narrative and the hard-coded
`demo-mission-001` id. It now drives the real async service layer with the
configured `meridian-industrial` / `kestrel-components` identity.

Note the collection fix: `pytest.ini` previously set
`python_files = sprint_*.py`, so every `tests/test_*.py` file in this directory
was silently never collected. It now lists both conventions, which is why this
file keeps its `sprint_` name.
"""

from __future__ import annotations

from conftest import requires_backend

requires_backend()

from nexus_api.core.config import settings  # noqa: E402
from nexus_api.schemas.domain import (  # noqa: E402
    ApprovalDecisionRequest,
    ApprovalStatus,
    EventType,
    MissionStatus,
    PolicyOutcome,
    StartMissionRequest,
    TaskStatus,
)
from nexus_api.services.mission import mission_service  # noqa: E402
from nexus_api.services.policy import evaluate_policy  # noqa: E402
from nexus_api.services.storage import store  # noqa: E402

TIMEOUT = 60.0


def test_roster_seeds_twenty_agents(seeded_store):
    assert len(store.list_agents()) == 20
    assert {agent.tier.value for agent in store.list_agents()} == {1, 2, 3}


def test_policy_gateway_has_allow_deny_and_approval_outcomes(seeded_store):
    allowed = evaluate_policy(
        "david-brooks", "financial_lookup", {"vendorId": settings.default_vendor_id}
    )
    approval = evaluate_policy(
        "david-brooks", "create_payment", {"amount": 500000, "currency": "INR"}
    )
    denied = evaluate_policy("elena-rao", "bank-account.read", {})

    assert allowed.outcome == PolicyOutcome.allow
    assert approval.outcome == PolicyOutcome.require_approval
    assert denied.outcome == PolicyOutcome.deny


async def test_vendor_mission_pauses_for_human_approval_then_completes(seeded_store):
    """The governance vertical slice at the service layer.

    `start_mission` is now async and returns immediately, so the mission is
    settled with `wait_for_mission` instead of being assumed complete.
    """
    mission_service.seed_demo()

    mission = await mission_service.start_mission(StartMissionRequest())
    assert mission.status == MissionStatus.created, "start_mission must not block"

    parked = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert parked.id == mission.id
    assert parked.id != "demo-mission-001"
    assert parked.enterpriseId == settings.enterprise_id
    assert parked.vendorId == settings.default_vendor_id
    assert parked.status == MissionStatus.awaiting_approval
    assert parked.awaitingApprovalId is not None
    assert len(store.list_approvals(ApprovalStatus.pending)) == 1

    completed = mission_service.decide_approval(
        parked.awaitingApprovalId,
        ApprovalDecisionRequest(decision="granted", decidedBy="operator"),
    )
    assert completed.id == mission.id

    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert settled.status == MissionStatus.completed
    assert all(task.status == TaskStatus.completed for task in settled.tasks)

    event_types = [event.type for event in store.list_events(settled.id)]
    for expected in (
        EventType.mission_created,
        EventType.plan_created,
        EventType.security_alert,
        EventType.approval_requested,
        EventType.approval_granted,
        EventType.mission_completed,
    ):
        assert expected in event_types, f"missing {expected.value}"


async def test_seed_demo_clears_previous_state(seeded_store):
    mission = await mission_service.start_mission(StartMissionRequest())
    await mission_service.wait_for_mission(mission.id, TIMEOUT)
    assert store.list_missions()

    mission_service.seed_demo()

    assert store.list_missions() == []
    assert store.list_approvals() == []
    assert len(store.list_agents()) == 20
