"""The full end-to-end mission walkthrough, over HTTP, exactly as the demo runs.

SANDBOX NOTE: authored where pytest/pydantic/fastapi/httpx were unavailable, so
this file was NOT executed at authoring time. See tests/conftest.py.

This file replaces the old `demo-mission-001` / `wayne-enterprises` /
`acme-technologies` walkthrough. Three things changed in the backend and all
three are asserted here:

  1. mission ids are generated, so the audit endpoint is addressed by the id the
     API returned — never by a hard-coded constant;
  2. `POST /api/missions` answers **202** with a `created` mission, so progress is
     observed by polling instead of assumed to be finished;
  3. the enterprise and vendor identity come from configuration
     (`meridian-industrial` / `kestrel-components`).
"""

from __future__ import annotations

from conftest import poll_mission, requires_api

requires_api()

from nexus_api.core.config import settings  # noqa: E402

TIMEOUT = 60.0


def test_vendor_onboarding_mission_pauses_for_a_human_then_completes(live_client):
    # 1. seed the roster
    seed = live_client.post("/api/demo/seed")
    assert seed.status_code == 200
    assert seed.json()["agents"] == 20

    # 2. start the mission — accepted, not finished
    start = live_client.post("/api/missions", json={})
    assert start.status_code == 202
    created = start.json()
    mission_id = created["id"]
    assert created["status"] == "created"
    assert mission_id.startswith("mission-")
    assert mission_id != "demo-mission-001"
    assert created["enterpriseId"] == settings.enterprise_id == "meridian-industrial"
    assert created["vendorId"] == settings.default_vendor_id == "kestrel-components"

    # 3. the server plans and runs it in the background, and parks on approval
    parked = poll_mission(live_client, mission_id, TIMEOUT)
    assert parked["status"] == "awaiting_approval"
    assert parked["awaitingApprovalId"]
    assert parked["planSource"] in {"gemini", "deterministic_fallback"}
    assert len(parked["tasks"]) >= 3
    assert len(parked["plan"]) == len(parked["tasks"])

    statuses = {task["id"]: task["status"] for task in parked["tasks"]}
    assert statuses["task-research"] == "completed"
    assert statuses["task-compliance"] == "completed", (
        "the compliance branch must finish even though the finance branch parked"
    )
    assert statuses["task-finance"] == "blocked"

    # 4. exactly one approval is pending, and it is the high-risk payment
    approvals = live_client.get("/api/approvals", params={"status": "pending"}).json()
    assert len(approvals) == 1
    approval = approvals[0]
    assert approval["tool"] == "create_payment"
    assert approval["agentId"] == "david-brooks"
    assert approval["missionId"] == mission_id
    assert approval["taskId"] == "task-finance"
    assert approval["risk"] == "HIGH"
    assert approval["request"]["amount"] > 100000

    # the payment has not run
    audit = live_client.get(f"/api/missions/{mission_id}/audit").json()
    assert _payment_calls(audit) == 0

    # 5. the operator grants it
    decision = live_client.post(
        f"/api/approvals/{approval['id']}/decision",
        json={"decision": "granted", "decidedBy": "operator"},
    )
    assert decision.status_code == 200

    # 6. the mission resumes and completes
    completed = poll_mission(live_client, mission_id, TIMEOUT)
    assert completed["status"] == "completed"
    assert completed["completedAt"]
    assert completed["currentStep"] == len(completed["tasks"])
    assert all(task["status"] == "completed" for task in completed["tasks"])
    assert completed["awaitingApprovalId"] is None

    # 7. the audit trail tells the whole story, addressed by the real id
    audit = live_client.get(f"/api/missions/{mission_id}/audit").json()
    assert audit["mission"]["id"] == mission_id
    event_types = [event["type"] for event in audit["events"]]
    for expected in (
        "MISSION_CREATED",
        "PLAN_CREATED",
        "AGENT_STARTED",
        "POLICY_CHECK",
        "POLICY_ALLOWED",
        "TOOL_STARTED",
        "TOOL_COMPLETED",
        "AGENT_MESSAGE",
        "SECURITY_ALERT",
        "POLICY_BLOCKED",
        "APPROVAL_REQUESTED",
        "MISSION_PAUSED",
        "APPROVAL_GRANTED",
        "AGENT_RESUMED",
        "MISSION_RESUMED",
        "AGENT_COMPLETED",
        "MISSION_COMPLETED",
    ):
        assert expected in event_types, f"missing {expected} in the audit trail"

    assert "CIRCUIT_BREAKER_TRIPPED" not in event_types
    assert "MISSION_FAILED" not in event_types
    assert _payment_calls(audit) == 1, "the approved payment must run exactly once"
    assert all(event["missionId"] == mission_id for event in audit["events"])
    # Chronological, so the trail reads as a story rather than a set.
    timestamps = [event["timestamp"] for event in audit["events"]]
    assert timestamps == sorted(timestamps)


def test_two_missions_can_run_and_be_audited_independently(live_client):
    first = live_client.post("/api/missions", json={}).json()["id"]
    second = live_client.post(
        "/api/missions",
        json={
            "title": "MediSupply Emergency Qualification",
            "objective": "Verify the supplier and clear sanctions and compliance.",
            "vendorId": "medisupply-corp",
        },
    ).json()["id"]

    assert first != second
    poll_mission(live_client, first, TIMEOUT)
    poll_mission(live_client, second, TIMEOUT)

    for mission_id in (first, second):
        audit = live_client.get(f"/api/missions/{mission_id}/audit").json()
        assert audit["mission"]["id"] == mission_id
        assert {event["missionId"] for event in audit["events"]} == {mission_id}

    listed = {mission["id"] for mission in live_client.get("/api/missions").json()}
    assert {first, second}.issubset(listed)


def _payment_calls(audit: dict) -> int:
    return len(
        [
            event
            for event in audit["events"]
            if event["type"] == "TOOL_COMPLETED"
            and event["metadata"].get("tool") == "create_payment"
        ]
    )
