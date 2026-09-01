def test_acme_mission_pauses_for_approval_then_completes(client):
    seed = client.post("/api/demo/seed")
    assert seed.status_code == 200

    start = client.post(
        "/api/missions",
        json={
            "enterpriseId": "wayne-enterprises",
            "title": "ACME Vendor Onboarding",
            "objective": "Evaluate ACME Technologies and onboard if compliant.",
            "vendorId": "acme-technologies",
        },
    )
    assert start.status_code == 200
    mission = start.json()
    assert mission["status"] == "awaiting_approval"
    assert mission["awaitingApprovalId"]

    approvals = client.get("/api/approvals").json()
    assert len(approvals) == 1
    approval_id = approvals[0]["id"]
    assert approvals[0]["tool"] == "create_payment"

    completed = client.post(
        f"/api/approvals/{approval_id}/decision",
        json={"decision": "granted", "decidedBy": "operator"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    audit = client.get("/api/missions/demo-mission-001/audit").json()
    event_types = [event["type"] for event in audit["events"]]
    assert "MISSION_CREATED" in event_types
    assert "SECURITY_ALERT" in event_types
    assert "APPROVAL_REQUESTED" in event_types
    assert "APPROVAL_GRANTED" in event_types
    assert "MISSION_COMPLETED" in event_types

