"""Tool execution — the single choke point for agent side effects.

Every tool call in NEXUS goes through `execute_tool`, and `execute_tool` always
evaluates the least-privilege policy first. Nothing (planner, orchestrator, HTTP
route) is allowed to call `_dispatch_tool` directly.

Three properties are enforced here:
  1. DENY is terminal — it is checked before any approval handling, so a denied
     call can never be turned into an allowed one by retrying or by presenting an
     approval token.
  2. REQUIRE_APPROVAL creates a pending `Approval` and raises
     `ApprovalRequiredError`, carrying the approval id so the orchestrator can
     park exactly the right branch.
  3. An approval token is *verified* (right mission, agent, tool, and granted)
     before it is honoured. An unverifiable token is treated as a policy
     violation, not as consent.
"""

import json
from pathlib import Path
from typing import Any

from nexus_api.core.config import settings
from nexus_api.core.logging import get_logger
from nexus_api.schemas.domain import Approval, ApprovalStatus, EventType, PolicyOutcome
from nexus_api.services.events import event_bus
from nexus_api.services.policy import (
    ApprovalRequiredError,
    PolicyViolationError,
    emit_policy_decision,
    evaluate_policy,
)
from nexus_api.services.storage import DATA_DIR, store

logger = get_logger("tools")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_approval(
    approval_id: str, mission_id: str, agent_id: str, tool: str
) -> tuple[bool, str]:
    """Confirm an approval token really authorises *this* call."""
    try:
        approval = store.get_approval(approval_id)
    except KeyError:
        return False, "unknown_approval_id"
    if approval.missionId != mission_id:
        return False, "approval_mission_mismatch"
    if approval.agentId != agent_id:
        return False, "approval_agent_mismatch"
    if approval.tool != tool:
        return False, "approval_tool_mismatch"
    if approval.status != ApprovalStatus.granted:
        return False, f"approval_not_granted:{approval.status.value}"
    return True, "approval_verified"


def execute_tool(
    mission_id: str,
    agent_id: str,
    tool: str,
    payload: dict[str, Any],
    approved_approval_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    decision = evaluate_policy(agent_id, tool, payload)
    emit_policy_decision(mission_id, decision)

    # (1) DENY first, and always. No token and no retry can change this.
    if decision.outcome == PolicyOutcome.deny:
        logger.warning(
            "tools.denied",
            missionId=mission_id,
            agentId=agent_id,
            tool=tool,
            reason=decision.reason,
        )
        raise PolicyViolationError(decision.reason)

    if decision.outcome == PolicyOutcome.require_approval:
        if approved_approval_id is None:
            approval = Approval(
                missionId=mission_id,
                agentId=agent_id,
                tool=tool,
                request=payload,
                reason=decision.reason,
                policyId=decision.policyId,
                taskId=task_id,
            )
            store.save_approval(approval)
            event_bus.emit(
                EventType.approval_requested,
                mission_id,
                f"Approval required for {tool}",
                agent_id,
                metadata={
                    "approvalId": approval.id,
                    "taskId": task_id,
                    "request": _redact(payload),
                    "reason": decision.reason,
                },
            )
            logger.info(
                "tools.approval_requested",
                missionId=mission_id,
                agentId=agent_id,
                tool=tool,
                approvalId=approval.id,
            )
            raise ApprovalRequiredError(decision, approval.id)

        # (3) A token is only consent if it verifies.
        verified, verdict = _verify_approval(approved_approval_id, mission_id, agent_id, tool)
        if not verified:
            event_bus.emit(
                EventType.policy_blocked,
                mission_id,
                f"{tool} blocked: presented approval token is not valid ({verdict})",
                agent_id,
                metadata={
                    "tool": tool,
                    "approvalId": approved_approval_id,
                    "reason": verdict,
                },
            )
            logger.warning(
                "tools.invalid_approval_token",
                missionId=mission_id,
                agentId=agent_id,
                tool=tool,
                approvalId=approved_approval_id,
                verdict=verdict,
            )
            raise PolicyViolationError(f"invalid_approval_token:{verdict}")

    event_bus.emit(
        EventType.tool_started,
        mission_id,
        f"{tool} started",
        agent_id,
        metadata={"tool": tool, "taskId": task_id, "payload": _redact(payload)},
    )
    result = _dispatch_tool(tool, payload)
    event_bus.emit(
        EventType.tool_completed,
        mission_id,
        f"{tool} completed",
        agent_id,
        metadata={
            "tool": tool,
            "taskId": task_id,
            "result": result,
            "approvedBy": approved_approval_id,
        },
    )
    return result


def _dispatch_tool(tool: str, payload: dict[str, Any]) -> dict[str, Any]:
    vendor_id = payload.get("vendorId") or payload.get("companyId") or settings.default_vendor_id
    vendors = _load_json(DATA_DIR / "synthetic" / "vendors.json")

    if tool in {"company_search", "company_profile"}:
        if vendor_id in vendors:
            return vendors[vendor_id]
        return {
            "id": vendor_id,
            "name": vendor_id.replace("-", " ").title(),
            "registration": f"ROC-GEN-{abs(hash(vendor_id)) % 1000000:06d}",
            "domain": f"{vendor_id}.example.com",
            "employees": 250,
            "annualRevenueUsd": 8500000,
            "status": "synthetic_generated",
        }
    if tool == "document_search":
        return {"documents": ["malicious_vendor_document.txt"], "vendorId": vendor_id}
    if tool == "policy_search":
        return {"policies": ["finance-strict", "procurement-default"]}
    if tool == "sanctions_check":
        return {"vendorId": vendor_id, "sanctionsStatus": "clear"}
    if tool == "compliance_check":
        return {"vendorId": vendor_id, "score": 82, "decision": "pass"}
    if tool == "financial_lookup":
        record = vendors.get(vendor_id, {})
        return {
            "vendorId": vendor_id,
            "annualRevenueUsd": record.get("annualRevenueUsd", 12400000),
            "cashflow": record.get("cashflow", "stable"),
        }
    if tool == "risk_calculator":
        return {"vendorId": vendor_id, "riskScore": 75, "riskLevel": "medium"}
    if tool == "invoice_analysis":
        return {"invoiceId": payload.get("invoiceId", "synthetic-invoice-001"), "status": "clean"}
    if tool == "create_payment":
        return {
            "paymentId": "synthetic-payment-001",
            "status": "approved_for_demo",
            "amount": payload.get("amount"),
            "currency": payload.get("currency"),
        }
    if tool == "supplier_score":
        return {"vendorId": vendor_id, "supplierScore": 87, "decision": "recommended"}
    if tool == "contract_generator":
        return {"contractId": "synthetic-contract-001", "status": "drafted"}
    if tool == "contract_finalize":
        return {
            "contractId": payload.get("contractId", "synthetic-contract-001"),
            "status": "finalized",
        }

    raise ValueError(f"Unknown tool: {tool}")


def _redact(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(payload)
    for key in ("apiKey", "secret", "token", "accountNumber", "iban"):
        if key in redacted:
            redacted[key] = "[REDACTED]"
    return redacted
