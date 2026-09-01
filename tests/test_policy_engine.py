"""Policy gate: ALLOW / DENY / REQUIRE_APPROVAL, and the ways an attacker would
try to get around them.

SANDBOX NOTE: authored where pytest/pydantic were unavailable, so this file was
NOT executed at authoring time. It requires `pydantic` (see tests/conftest.py).

What this file proves:
  * the three policy outcomes are reachable with the real roster and rules;
  * a DENY stays a DENY across repeated calls — retrying is not an escalation
    path, and `TOOL_COMPLETED` is never emitted for a denied tool;
  * a DENY cannot be converted into an ALLOW by presenting an approval token;
  * forged / mismatched / still-pending approval tokens are all refused by
    `execute_tool`, and each refusal is auditable as `POLICY_BLOCKED`.
"""

from __future__ import annotations

import pytest

from conftest import requires_backend

requires_backend()

from nexus_api.schemas.domain import (  # noqa: E402
    Approval,
    ApprovalStatus,
    EventType,
    PolicyOutcome,
)
from nexus_api.services.policy import (  # noqa: E402
    ApprovalRequiredError,
    PolicyViolationError,
    evaluate_policy,
)
from nexus_api.services.storage import store  # noqa: E402
from nexus_api.services.tools import execute_tool  # noqa: E402

MISSION = "mission-policy-test"
PAYMENT = {
    "vendorId": "kestrel-components",
    "recipient": "kestrel-components",
    "amount": 500000,
    "currency": "INR",
}


def _types(mission_id: str = MISSION) -> list[EventType]:
    return [event.type for event in store.list_events(mission_id)]


def _completed_tools(mission_id: str = MISSION) -> list[str]:
    return [
        event.metadata.get("tool")
        for event in store.list_events(mission_id)
        if event.type == EventType.tool_completed
    ]


# ── the three outcomes ──────────────────────────────────────────────────────


def test_finance_read_is_allowed(seeded_store):
    decision = evaluate_policy(
        "david-brooks", "financial_lookup", {"vendorId": "kestrel-components"}
    )

    assert decision.outcome == PolicyOutcome.allow
    assert decision.policyId == "finance-strict"
    assert decision.capability == "financial.read"


def test_payment_above_threshold_requires_approval(seeded_store):
    decision = evaluate_policy("david-brooks", "create_payment", PAYMENT)

    assert decision.outcome == PolicyOutcome.require_approval
    assert decision.metadata["threshold"] == 100000


def test_payment_below_threshold_does_not_require_approval(seeded_store):
    decision = evaluate_policy(
        "david-brooks", "create_payment", {**PAYMENT, "amount": 500}
    )

    assert decision.outcome != PolicyOutcome.require_approval


def test_out_of_scope_capability_is_denied(seeded_store):
    decision = evaluate_policy("elena-rao", "bank-account.read", {})

    assert decision.outcome == PolicyOutcome.deny
    assert decision.reason == "identity_scope_violation"


def test_research_agent_cannot_reach_the_payment_tool(seeded_store):
    """Cross-department escalation attempt at the policy layer."""
    decision = evaluate_policy("elena-rao", "create_payment", PAYMENT)

    assert decision.outcome == PolicyOutcome.deny


def test_contract_finalize_requires_approval_with_no_threshold(seeded_store):
    decision = evaluate_policy("sarah-patel", "contract_finalize", {})

    assert decision.outcome == PolicyOutcome.require_approval
    assert decision.metadata["threshold"] is None


def test_agent_outside_the_rule_table_gets_default_deny(seeded_store):
    """A tier-3 registry agent has no policy rule and no runnable tool."""
    decision = evaluate_policy("iris-vance", "create_payment", PAYMENT)

    assert decision.outcome == PolicyOutcome.deny
    assert decision.policyId == "default-deny"


# ── DENY is terminal: retry is not an escalation path ───────────────────────


def test_denied_tool_stays_denied_across_repeated_calls(seeded_store):
    """The hostile-judge case: hammer the same denied call and check that the
    outcome never flips and that no side effect is ever recorded."""
    attempts = 12

    for _ in range(attempts):
        with pytest.raises(PolicyViolationError):
            execute_tool(MISSION, "elena-rao", "create_payment", PAYMENT)

    types = _types()
    assert types.count(EventType.policy_blocked) == attempts
    assert EventType.policy_allowed not in types
    assert EventType.tool_started not in types, "a denied call must never start the tool"
    assert EventType.tool_completed not in types
    assert _completed_tools() == []
    # And no approval was ever created, so there is nothing for an operator to
    # accidentally grant.
    assert store.list_approvals() == []


def test_denied_tool_cannot_be_unlocked_by_a_granted_token(seeded_store):
    """DENY is evaluated before any approval handling, so even a real, granted,
    perfectly-matching approval record must not launder a denied call."""
    approval = Approval(
        missionId=MISSION,
        agentId="elena-rao",
        tool="create_payment",
        request=PAYMENT,
        reason="forged",
        policyId="research-default",
        status=ApprovalStatus.granted,
        decision=ApprovalStatus.granted,
    )
    store.save_approval(approval)

    with pytest.raises(PolicyViolationError):
        execute_tool(
            MISSION, "elena-rao", "create_payment", PAYMENT, approved_approval_id=approval.id
        )

    assert EventType.tool_completed not in _types()
    assert _completed_tools() == []


def test_denied_call_reason_is_recorded_for_audit(seeded_store):
    with pytest.raises(PolicyViolationError):
        execute_tool(MISSION, "elena-rao", "create_payment", PAYMENT)

    blocked = [
        event for event in store.list_events(MISSION) if event.type == EventType.policy_blocked
    ]
    assert blocked
    assert blocked[-1].metadata["reason"] in {
        "identity_scope_violation",
        "explicit_deny",
        "default_deny_no_explicit_allow",
    }


# ── approval flow: the honest path ──────────────────────────────────────────


def test_approval_required_creates_exactly_one_pending_approval(seeded_store):
    with pytest.raises(ApprovalRequiredError) as excinfo:
        execute_tool(MISSION, "david-brooks", "create_payment", PAYMENT, task_id="task-finance")

    approvals = store.list_approvals(ApprovalStatus.pending)
    assert len(approvals) == 1
    assert excinfo.value.approvalId == approvals[0].id
    assert approvals[0].tool == "create_payment"
    assert approvals[0].agentId == "david-brooks"
    assert approvals[0].taskId == "task-finance"
    assert approvals[0].missionId == MISSION

    types = _types()
    assert EventType.approval_requested in types
    assert EventType.tool_started not in types, "the tool must not run before the decision"
    assert EventType.tool_completed not in types


def test_a_properly_granted_token_lets_the_tool_run_once(seeded_store):
    with pytest.raises(ApprovalRequiredError) as excinfo:
        execute_tool(MISSION, "david-brooks", "create_payment", PAYMENT)
    approval_id = excinfo.value.approvalId

    approval = store.get_approval(approval_id)
    approval.status = ApprovalStatus.granted
    approval.decision = ApprovalStatus.granted
    store.save_approval(approval)

    result = execute_tool(
        MISSION, "david-brooks", "create_payment", PAYMENT, approved_approval_id=approval_id
    )

    assert result["status"] == "approved_for_demo"
    assert _completed_tools().count("create_payment") == 1
    completed = [
        event
        for event in store.list_events(MISSION)
        if event.type == EventType.tool_completed
    ]
    assert completed[-1].metadata["approvedBy"] == approval_id


def test_approval_request_payload_is_redacted_in_the_event_log(seeded_store):
    with pytest.raises(ApprovalRequiredError):
        execute_tool(
            MISSION,
            "david-brooks",
            "create_payment",
            {**PAYMENT, "accountNumber": "1234567890", "secret": "hunter2"},
        )

    requested = [
        event
        for event in store.list_events(MISSION)
        if event.type == EventType.approval_requested
    ]
    logged = requested[-1].metadata["request"]
    assert logged["accountNumber"] == "[REDACTED]"
    assert logged["secret"] == "[REDACTED]"
    assert logged["amount"] == 500000


# ── forged approval tokens ──────────────────────────────────────────────────


def _grant(**overrides) -> Approval:
    fields = {
        "missionId": MISSION,
        "agentId": "david-brooks",
        "tool": "create_payment",
        "request": PAYMENT,
        "reason": "Payments above threshold require human approval",
        "policyId": "finance-strict",
        "status": ApprovalStatus.granted,
        "decision": ApprovalStatus.granted,
    }
    fields.update(overrides)
    approval = Approval(**fields)
    store.save_approval(approval)
    return approval


def test_unknown_approval_id_is_refused(seeded_store):
    with pytest.raises(PolicyViolationError) as excinfo:
        execute_tool(
            MISSION,
            "david-brooks",
            "create_payment",
            PAYMENT,
            approved_approval_id="appr-deadbeefcafe",
        )

    assert "unknown_approval_id" in str(excinfo.value)
    assert EventType.tool_completed not in _types()
    assert _completed_tools() == []


def test_still_pending_approval_id_is_refused(seeded_store):
    """Presenting your own not-yet-decided approval must not self-authorise."""
    with pytest.raises(ApprovalRequiredError) as excinfo:
        execute_tool(MISSION, "david-brooks", "create_payment", PAYMENT)
    pending_id = excinfo.value.approvalId
    assert store.get_approval(pending_id).status == ApprovalStatus.pending

    with pytest.raises(PolicyViolationError) as refused:
        execute_tool(
            MISSION, "david-brooks", "create_payment", PAYMENT, approved_approval_id=pending_id
        )

    assert "approval_not_granted:pending" in str(refused.value)
    assert _completed_tools() == []


def test_denied_approval_id_is_refused(seeded_store):
    approval = _grant(status=ApprovalStatus.denied, decision=ApprovalStatus.denied)

    with pytest.raises(PolicyViolationError) as excinfo:
        execute_tool(
            MISSION, "david-brooks", "create_payment", PAYMENT, approved_approval_id=approval.id
        )

    assert "approval_not_granted:denied" in str(excinfo.value)
    assert _completed_tools() == []


def test_approval_granted_for_a_different_agent_is_refused(seeded_store):
    """The impersonation case: a real, granted approval belonging to procurement
    must not authorise a finance tool call."""
    approval = _grant(agentId="sarah-patel")

    with pytest.raises(PolicyViolationError) as excinfo:
        execute_tool(
            MISSION, "david-brooks", "create_payment", PAYMENT, approved_approval_id=approval.id
        )

    assert "approval_agent_mismatch" in str(excinfo.value)
    assert _completed_tools() == []
    blocked = [
        event for event in store.list_events(MISSION) if event.type == EventType.policy_blocked
    ]
    assert blocked[-1].metadata["reason"] == "approval_agent_mismatch"
    assert blocked[-1].metadata["approvalId"] == approval.id


def test_approval_granted_for_a_different_mission_is_refused(seeded_store):
    """Replaying yesterday's approval against a new mission must fail."""
    approval = _grant(missionId="mission-some-other-run")

    with pytest.raises(PolicyViolationError) as excinfo:
        execute_tool(
            MISSION, "david-brooks", "create_payment", PAYMENT, approved_approval_id=approval.id
        )

    assert "approval_mission_mismatch" in str(excinfo.value)
    assert _completed_tools() == []


def test_approval_granted_for_a_different_tool_is_refused(seeded_store):
    approval = _grant(tool="invoice_analysis")

    with pytest.raises(PolicyViolationError) as excinfo:
        execute_tool(
            MISSION, "david-brooks", "create_payment", PAYMENT, approved_approval_id=approval.id
        )

    assert "approval_tool_mismatch" in str(excinfo.value)
    assert _completed_tools() == []


def test_a_granted_token_is_not_reusable_for_a_second_high_risk_tool(seeded_store):
    """One grant authorises one tool. `contract_finalize` also requires approval,
    so the finance grant must not carry over to procurement."""
    approval = _grant()

    with pytest.raises(PolicyViolationError):
        execute_tool(
            MISSION,
            "sarah-patel",
            "contract_finalize",
            {},
            approved_approval_id=approval.id,
        )

    assert "contract_finalize" not in _completed_tools()


def test_every_forged_token_refusal_is_auditable(seeded_store):
    """Each rejected token leaves a POLICY_BLOCKED record naming the verdict, so
    an auditor can see attempted bypasses rather than only successful calls."""
    forged = [
        ("appr-nope", "unknown_approval_id"),
        (_grant(agentId="sarah-patel").id, "approval_agent_mismatch"),
        (_grant(missionId="mission-elsewhere").id, "approval_mission_mismatch"),
        (_grant(tool="invoice_analysis").id, "approval_tool_mismatch"),
        (
            _grant(status=ApprovalStatus.denied, decision=ApprovalStatus.denied).id,
            "approval_not_granted:denied",
        ),
    ]

    for token, _ in forged:
        with pytest.raises(PolicyViolationError):
            execute_tool(
                MISSION, "david-brooks", "create_payment", PAYMENT, approved_approval_id=token
            )

    reasons = [
        event.metadata.get("reason")
        for event in store.list_events(MISSION)
        if event.type == EventType.policy_blocked
    ]
    for _, expected in forged:
        assert expected in reasons

    assert _completed_tools() == []


def test_policy_check_event_is_emitted_for_every_decision(seeded_store):
    execute_tool(MISSION, "elena-rao", "company_search", {"vendorId": "kestrel-components"})
    with pytest.raises(ApprovalRequiredError):
        execute_tool(MISSION, "david-brooks", "create_payment", PAYMENT)
    with pytest.raises(PolicyViolationError):
        execute_tool(MISSION, "elena-rao", "create_payment", PAYMENT)

    types = _types()
    assert types.count(EventType.policy_check) == 3
    assert EventType.policy_allowed in types
    assert EventType.policy_blocked in types


def test_unknown_tool_name_is_denied_before_dispatch(seeded_store):
    """`_dispatch_tool` raises ValueError for an unknown tool, but the policy gate
    must reject it first so an unknown tool is never even attempted."""
    with pytest.raises(PolicyViolationError):
        execute_tool(MISSION, "elena-rao", "totally_made_up_tool", {})

    assert EventType.tool_started not in _types()
