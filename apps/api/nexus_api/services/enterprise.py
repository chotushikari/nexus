"""Enterprise identity and aggregate counts.

The frontend header must not hard-code a company name, a department list, or a
badge count. Everything it needs comes from here, and the identity itself comes
from `core/config.py` (`settings.enterprise_id` / `settings.enterprise_name`).
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from nexus_api.core.config import settings
from nexus_api.core.logging import get_logger
from nexus_api.schemas.domain import (
    DepartmentCard,
    EnterpriseCounts,
    EnterpriseSummary,
    EventType,
    MissionStatus,
    RuntimeStatus,
)
from nexus_api.services.capabilities import capabilities
from nexus_api.services.storage import DATA_DIR, store

logger = get_logger("enterprise")

ACTIVE_MISSION_STATUSES = {
    MissionStatus.created,
    MissionStatus.planning,
    MissionStatus.running,
    MissionStatus.awaiting_approval,
    MissionStatus.paused,
}

BUSY_RUNTIME_STATUSES = {
    RuntimeStatus.planning,
    RuntimeStatus.working,
    RuntimeStatus.communicating,
    RuntimeStatus.waiting,
    RuntimeStatus.approval_required,
}


def load_departments() -> list[DepartmentCard]:
    """Departments come from `data/departments.json` (schema unchanged)."""
    path = DATA_DIR / "departments.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("enterprise.departments_unreadable", path=str(path), reason=str(exc))
        return []

    if not store.agents:
        store.seed_agents_from_roster()
    per_department: dict[str, int] = {}
    for agent in store.list_agents():
        per_department[agent.departmentId] = per_department.get(agent.departmentId, 0) + 1

    departments: list[DepartmentCard] = []
    for item in payload if isinstance(payload, list) else []:
        try:
            card = DepartmentCard.model_validate(item)
        except ValidationError as exc:
            logger.warning(
                "enterprise.department_invalid", departmentId=item.get("id"), reason=str(exc)
            )
            continue
        card.agentCount = per_department.get(card.id, 0)
        departments.append(card)
    return departments


def aggregate_counts(departments: list[DepartmentCard] | None = None) -> EnterpriseCounts:
    if not store.agents:
        store.seed_agents_from_roster()
    agents = store.list_agents()
    missions = store.list_missions()
    departments = departments if departments is not None else load_departments()

    busy: set[str] = set()
    for mission in missions:
        if mission.status not in ACTIVE_MISSION_STATUSES:
            continue
        for agent_id, state in mission.agentStates.items():
            if state in BUSY_RUNTIME_STATUSES:
                busy.add(agent_id)

    security_alerts = len(
        [event for event in store.list_events() if event.type == EventType.security_alert]
    )

    return EnterpriseCounts(
        agentsTotal=len(agents),
        agentsOnline=len([agent for agent in agents if str(agent.status) == "approved"]),
        agentsBusy=len(busy),
        missionsTotal=len(missions),
        missionsActive=len(
            [mission for mission in missions if mission.status in ACTIVE_MISSION_STATUSES]
        ),
        approvalsPending=len(
            [approval for approval in store.list_approvals() if approval.status.value == "pending"]
        ),
        securityAlerts=security_alerts,
        departments=len(departments),
    )


def enterprise_summary() -> EnterpriseSummary:
    departments = load_departments()
    return EnterpriseSummary(
        id=settings.enterprise_id,
        name=settings.enterprise_name,
        environment=settings.environment,
        demoMode=settings.demo_mode,
        defaultVendorId=settings.default_vendor_id,
        defaultVendorName=settings.default_vendor_name,
        departments=departments,
        counts=aggregate_counts(departments),
        capabilities=capabilities.report(),
        storeBackend=store.backend,
    )
