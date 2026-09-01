from dataclasses import dataclass
from typing import Any

from nexus_api.schemas.domain import EventType, PolicyDecision, PolicyOutcome
from nexus_api.services.events import event_bus
from nexus_api.services.storage import store


TOOL_CAPABILITIES: dict[str, str] = {
    "mission.plan": "mission.create",
    "task.delegate": "task.delegate",
    "approval.request": "approval.request",
    "company_search": "public_company.read",
    "document_search": "document.read",
    "company_profile": "research.read",
    "policy_search": "policy.read",
    "compliance_check": "compliance.read",
    "sanctions_check": "sanctions.check",
    "financial_lookup": "financial.read",
    "risk_calculator": "vendor-risk.read",
    "invoice_analysis": "invoice.read",
    "create_payment": "create_payment",
    "supplier_score": "supplier.score",
    "contract_generator": "contract.draft",
    "contract_finalize": "contract.finalize",
}


POLICY_RULES: dict[str, dict[str, Any]] = {
    "alex-morgan": {
        "policyId": "orchestrator-default",
        "allow": ["mission.create", "task.delegate", "approval.request"],
        "deny": ["tool.*.call", "payment.write", "contract.create"],
        "approvalRequired": [],
    },
    "elena-rao": {
        "policyId": "research-default",
        "allow": ["public_company.read", "research.read", "document.read"],
        "deny": ["finance.write", "payment.write", "contract.create"],
        "approvalRequired": [],
    },
    "marcus-chen": {
        "policyId": "compliance-default",
        "allow": ["policy.read", "compliance.read", "sanctions.check", "document.validate"],
        "deny": ["payment.write", "contract.create"],
        "approvalRequired": ["compliance_override"],
    },
    "david-brooks": {
        "policyId": "finance-strict",
        "allow": ["financial.read", "invoice.read", "vendor-risk.read"],
        "deny": ["payment.write", "bank-account.read", "payroll.write"],
        "approvalRequired": [
            {
                "tool": "create_payment",
                "threshold": 100000,
                "currency": "INR",
                "reason": "Payments above threshold require human approval",
            },
            {"tool": "contract.create", "reason": "Any contract creation requires human approval"},
        ],
    },
    "sarah-patel": {
        "policyId": "procurement-default",
        "allow": ["supplier.read", "supplier.score", "contract.draft"],
        "deny": ["payment.write"],
        "approvalRequired": [
            {"tool": "contract_finalize", "reason": "Contract finalization requires human approval"}
        ],
    },
}


@dataclass
class ApprovalRequiredError(Exception):
    """Raised by `execute_tool` when a call needs a human decision.

    `approvalId` lets the orchestrator park exactly the branch that stopped,
    instead of guessing from the tail of the approval list.
    """

    decision: PolicyDecision
    approvalId: str | None = None

    def __str__(self) -> str:
        return f"approval required for {self.decision.tool}: {self.decision.reason}"


class PolicyViolationError(Exception):
    pass


def evaluate_policy(agent_id: str, tool: str, payload: dict[str, Any]) -> PolicyDecision:
    agent = store.get_agent(agent_id)
    rule = POLICY_RULES.get(agent_id, {"policyId": "default-deny", "allow": [], "deny": []})
    capability = TOOL_CAPABILITIES.get(tool, tool)
    policy_id = rule["policyId"]

    for approval_rule in rule.get("approvalRequired", []):
        if isinstance(approval_rule, dict) and approval_rule["tool"] == tool:
            threshold = approval_rule.get("threshold")
            if threshold is None or payload.get("amount", 0) > threshold:
                return PolicyDecision(
                    outcome=PolicyOutcome.require_approval,
                    agentId=agent_id,
                    tool=tool,
                    capability=capability,
                    policyId=policy_id,
                    reason=approval_rule["reason"],
                    metadata={"threshold": threshold, "currency": approval_rule.get("currency")},
                )

    if capability not in agent.identity.scopes and tool not in agent.tools:
        return PolicyDecision(
            outcome=PolicyOutcome.deny,
            agentId=agent_id,
            tool=tool,
            capability=capability,
            policyId=policy_id,
            reason="identity_scope_violation",
        )

    if capability in rule.get("deny", []):
        return PolicyDecision(
            outcome=PolicyOutcome.deny,
            agentId=agent_id,
            tool=tool,
            capability=capability,
            policyId=policy_id,
            reason="explicit_deny",
        )

    if capability in rule.get("allow", []) or tool in agent.tools:
        return PolicyDecision(
            outcome=PolicyOutcome.allow,
            agentId=agent_id,
            tool=tool,
            capability=capability,
            policyId=policy_id,
            reason="explicit_allow",
        )

    return PolicyDecision(
        outcome=PolicyOutcome.deny,
        agentId=agent_id,
        tool=tool,
        capability=capability,
        policyId=policy_id,
        reason="default_deny_no_explicit_allow",
    )


def emit_policy_decision(mission_id: str, decision: PolicyDecision) -> None:
    event_bus.emit(
        EventType.policy_check,
        mission_id,
        f"{decision.tool} evaluated as {decision.outcome.value}",
        decision.agentId,
        metadata=decision.model_dump(mode="json"),
    )
    if decision.outcome == PolicyOutcome.allow:
        event_bus.emit(
            EventType.policy_allowed,
            mission_id,
            f"{decision.tool} allowed",
            decision.agentId,
            metadata=decision.model_dump(mode="json"),
        )
    elif decision.outcome == PolicyOutcome.deny:
        event_bus.emit(
            EventType.policy_blocked,
            mission_id,
            f"{decision.tool} blocked: {decision.reason}",
            decision.agentId,
            metadata=decision.model_dump(mode="json"),
        )

