"""HTTP contract tests.

SANDBOX NOTE: authored where pytest/pydantic/fastapi/httpx were unavailable, so
this file was NOT executed at authoring time. See tests/conftest.py.

Missions are asynchronous now, so `POST /api/missions` must answer **202
Accepted** with a `created` mission and let the server finish the work. These
tests use the polling helper rather than assuming the response is final; the old
suite asserted 200 plus a finished mission, which is no longer the contract.

They also pin the id contract: mission ids are generated per mission
(`mission-<12 hex>`), so nothing may look up the retired `demo-mission-001`.
"""

from __future__ import annotations

import json
import re

from conftest import poll_mission, requires_api

requires_api()

from nexus_api.core.config import settings  # noqa: E402

MISSION_ID = re.compile(r"^mission-[0-9a-f]{12}$")


def test_health_is_reachable(client):
    body = client.get("/api/health").json()

    assert body["status"] == "ok"
    assert body["service"] == "nexus-api"
    assert "capabilities" in body


def test_start_mission_is_accepted_not_completed(client, stub_execution):
    response = client.post("/api/missions", json={})

    assert response.status_code == 202, (
        "POST /api/missions must be 202 Accepted: planning and execution happen "
        "in a background task"
    )
    mission = response.json()
    assert MISSION_ID.match(mission["id"]), mission["id"]
    assert mission["status"] == "created"
    assert mission["tasks"] == [], "the response must not wait for a plan"
    assert mission["enterpriseId"] == settings.enterprise_id
    assert mission["vendorId"] == settings.default_vendor_id


def test_mission_ids_are_unique_per_request(client, stub_execution):
    ids = {client.post("/api/missions", json={}).json()["id"] for _ in range(4)}

    assert len(ids) == 4
    assert "demo-mission-001" not in ids
    for mission_id in ids:
        assert MISSION_ID.match(mission_id)


def test_retired_demo_mission_id_is_a_404(client):
    """`demo-mission-001` was the old hard-coded id. Nothing may resurrect it."""
    assert client.get("/api/missions/demo-mission-001").status_code == 404
    assert client.get("/api/missions/demo-mission-001/audit").status_code == 404


def test_unknown_mission_is_a_404(client):
    assert client.get("/api/missions/mission-000000000000").status_code == 404


def test_custom_mission_request_is_honoured(client, stub_execution):
    response = client.post(
        "/api/missions",
        json={
            "enterpriseId": "meridian-industrial",
            "title": "Emergency Supplier Qualification",
            "objective": "Qualify an emergency medical supplier and clear sanctions.",
            "vendorId": "medisupply-corp",
        },
    )

    assert response.status_code == 202
    mission = response.json()
    assert mission["title"] == "Emergency Supplier Qualification"
    assert mission["vendorId"] == "medisupply-corp"


def test_mission_events_endpoint_is_scoped_to_the_mission(live_client):
    first = live_client.post("/api/missions", json={}).json()["id"]
    second = live_client.post("/api/missions", json={}).json()["id"]
    poll_mission(live_client, first, timeout=60.0)
    poll_mission(live_client, second, timeout=60.0)

    for mission_id in (first, second):
        events = live_client.get(f"/api/missions/{mission_id}/events").json()
        assert events
        assert {event["missionId"] for event in events} == {mission_id}

    unfiltered = live_client.get("/api/events").json()
    assert {first, second}.issubset({event["missionId"] for event in unfiltered})
    filtered = live_client.get("/api/events", params={"mission_id": first}).json()
    assert {event["missionId"] for event in filtered} == {first}


def test_denying_an_approval_fails_the_mission_over_http(live_client):
    mission_id = live_client.post("/api/missions", json={}).json()["id"]
    poll_mission(live_client, mission_id, timeout=60.0)
    approval = live_client.get("/api/approvals", params={"status": "pending"}).json()[0]

    live_client.post(
        f"/api/approvals/{approval['id']}/decision",
        json={"decision": "denied", "decidedBy": "operator"},
    )
    settled = poll_mission(live_client, mission_id, timeout=60.0)

    assert settled["status"] == "failed"
    audit = live_client.get(f"/api/missions/{mission_id}/audit").json()
    assert "APPROVAL_DENIED" in [event["type"] for event in audit["events"]]


def test_unknown_approval_is_a_404(client):
    assert client.get("/api/approvals/appr-nope").status_code == 404
    assert (
        client.post(
            "/api/approvals/appr-nope/decision", json={"decision": "granted"}
        ).status_code
        == 404
    )


def test_approval_decision_rejects_an_invalid_verdict(client):
    response = client.post(
        "/api/approvals/appr-whatever/decision", json={"decision": "maybe"}
    )
    assert response.status_code == 422


# ── ad-hoc tool invocation still goes through the policy gate ───────────────


def test_adhoc_invoke_allows_an_in_scope_tool(client):
    response = client.post(
        "/api/agents/elena-rao/invoke",
        json={"tool": "company_search", "payload": {"vendorId": settings.default_vendor_id}},
    )

    assert response.status_code == 200
    assert response.json()["id"] == settings.default_vendor_id


def test_adhoc_invoke_is_403_for_a_denied_tool(client):
    """There must be no HTTP bypass around the policy gate."""
    response = client.post(
        "/api/agents/elena-rao/invoke",
        json={"tool": "create_payment", "payload": {"amount": 500000}},
    )

    assert response.status_code == 403
    assert "policy denied" in response.json()["detail"]


def test_adhoc_invoke_is_409_and_creates_an_approval_for_a_gated_tool(client):
    response = client.post(
        "/api/agents/david-brooks/invoke",
        json={
            "tool": "create_payment",
            "payload": {"amount": 500000, "currency": "INR"},
            "missionId": "mission-adhoc-test",
        },
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["approvalId"]
    approvals = client.get("/api/approvals").json()
    assert [approval["id"] for approval in approvals] == [detail["approvalId"]]


def test_adhoc_invoke_rejects_a_forged_approval_token(client):
    response = client.post(
        "/api/agents/david-brooks/invoke",
        json={
            "tool": "create_payment",
            "payload": {"amount": 500000, "currency": "INR"},
            "missionId": "mission-adhoc-test",
            "approved_approval_id": "appr-forged",
        },
    )

    assert response.status_code == 403
    assert "invalid_approval_token" in response.json()["detail"]


def test_adhoc_invoke_unknown_agent_is_404(client):
    response = client.post(
        "/api/agents/not-an-agent/invoke", json={"tool": "company_search"}
    )
    assert response.status_code == 404


# ── demo reset ──────────────────────────────────────────────────────────────


def test_demo_seed_reports_the_real_roster_size(client):
    body = client.post("/api/demo/seed").json()

    assert body["status"] == "seeded"
    assert body["agents"] == 20


def test_demo_reset_clears_missions_and_approvals(live_client):
    mission_id = live_client.post("/api/missions", json={}).json()["id"]
    poll_mission(live_client, mission_id, timeout=60.0)
    assert live_client.get("/api/approvals").json()

    live_client.post("/api/demo/reset")

    assert live_client.get("/api/missions").json() == []
    assert live_client.get("/api/approvals").json() == []
    assert live_client.get(f"/api/missions/{mission_id}").status_code == 404
    assert len(live_client.get("/api/agents").json()) == 20


# ── SSE stream ──────────────────────────────────────────────────────────────


def test_event_stream_replays_the_existing_events_on_connect(live_client):
    mission_id = live_client.post("/api/missions", json={}).json()["id"]
    poll_mission(live_client, mission_id, timeout=60.0)

    with live_client.stream(
        "GET", "/api/events/stream", params={"mission_id": mission_id}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        payloads = []
        for line in response.iter_lines():
            if line.startswith("data: "):
                payloads.append(line[len("data: ") :])
            if len(payloads) >= 3:
                break

    assert len(payloads) >= 3
    assert all(json.loads(payload)["missionId"] == mission_id for payload in payloads)
