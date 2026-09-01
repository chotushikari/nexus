from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from nexus_api.core.config import settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class AgentTier(int, Enum):
    core = 1
    extended = 2
    registry = 3


class AgentStatus(str, Enum):
    approved = "approved"
    experimental = "experimental"
    retired = "retired"
    registered_only = "registered_only"


class RuntimeStatus(str, Enum):
    idle = "IDLE"
    planning = "PLANNING"
    working = "WORKING"
    communicating = "COMMUNICATING"
    waiting = "WAITING"
    approval_required = "APPROVAL_REQUIRED"
    blocked = "BLOCKED"
    failed = "FAILED"
    completed = "COMPLETED"


class MissionStatus(str, Enum):
    created = "created"
    planning = "planning"
    running = "running"
    awaiting_approval = "awaiting_approval"
    completed = "completed"
    failed = "failed"
    paused = "paused"
    terminated = "terminated"


class TaskStatus(str, Enum):
    pending = "pending"
    ready = "ready"
    in_progress = "in_progress"
    blocked = "blocked"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class ApprovalStatus(str, Enum):
    pending = "pending"
    granted = "granted"
    denied = "denied"


class PlanSource(str, Enum):
    """Honest provenance of a mission plan. Never set `gemini` unless a Gemini
    response was actually received and validated."""

    gemini = "gemini"
    deterministic_fallback = "deterministic_fallback"


class EventType(str, Enum):
    mission_created = "MISSION_CREATED"
    plan_created = "PLAN_CREATED"
    agent_started = "AGENT_STARTED"
    agent_waiting = "AGENT_WAITING"
    agent_completed = "AGENT_COMPLETED"
    agent_failed = "AGENT_FAILED"
    agent_paused = "AGENT_PAUSED"
    agent_resumed = "AGENT_RESUMED"
    tool_started = "TOOL_STARTED"
    tool_completed = "TOOL_COMPLETED"
    tool_failed = "TOOL_FAILED"
    agent_message = "AGENT_MESSAGE"
    memory_read = "MEMORY_READ"
    memory_write = "MEMORY_WRITE"
    policy_check = "POLICY_CHECK"
    policy_allowed = "POLICY_ALLOWED"
    policy_blocked = "POLICY_BLOCKED"
    approval_requested = "APPROVAL_REQUESTED"
    approval_granted = "APPROVAL_GRANTED"
    approval_denied = "APPROVAL_DENIED"
    security_alert = "SECURITY_ALERT"
    mission_paused = "MISSION_PAUSED"
    mission_resumed = "MISSION_RESUMED"
    mission_completed = "MISSION_COMPLETED"
    mission_failed = "MISSION_FAILED"
    circuit_breaker_tripped = "CIRCUIT_BREAKER_TRIPPED"


class PolicyOutcome(str, Enum):
    allow = "ALLOW"
    deny = "DENY"
    require_approval = "REQUIRE_APPROVAL"


class Identity(BaseModel):
    principal: str
    scopes: list[str] = Field(default_factory=list)
    riskLevel: str = "low"


class Persona(BaseModel):
    tagline: str = ""
    inspiration: str = ""
    personality: list[str] = Field(default_factory=list)


class AgentCard(BaseModel):
    id: str
    name: str
    codename: str
    role: str
    departmentId: str
    tier: AgentTier
    status: AgentStatus | str
    version: str = "1.0.0"
    owner: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    dataScopes: list[str] = Field(default_factory=list)
    identity: Identity
    policies: list[str] = Field(default_factory=list)
    persona: Persona = Field(default_factory=Persona)
    unusualOperatorFit: str | None = None
    systemPromptPath: str | None = None


class Event(BaseModel):
    id: str = Field(default_factory=lambda: new_id("evt"))
    type: EventType
    timestamp: datetime = Field(default_factory=utc_now)
    missionId: str
    agentId: str | None = None
    targetAgentId: str | None = None
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class MissionPlanStep(BaseModel):
    """Flat projection of the task graph, kept for the existing UI contract.

    Derived from `Mission.tasks` — never the source of truth.
    """

    step: int
    agentId: str
    title: str
    status: Literal["pending", "in_progress", "completed", "blocked", "failed", "skipped"] = "pending"
    taskId: str | None = None
    dependsOn: list[str] = Field(default_factory=list)


class MissionTask(BaseModel):
    """A single node in the mission graph. Behaviour is entirely data-driven:
    the orchestrator reads `tools` and `agentId`, never a hard-coded branch."""

    id: str
    title: str
    agentId: str
    dependsOn: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    toolArgs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.pending
    attempts: int = 0
    maxAttempts: int = 3
    result: dict[str, Any] = Field(default_factory=dict)
    reasoning: str | None = None
    reasoningRuntime: str | None = None
    error: str | None = None
    awaitingApprovalId: str | None = None
    pendingTool: str | None = None
    startedAt: datetime | None = None
    completedAt: datetime | None = None


class Mission(BaseModel):
    id: str = Field(default_factory=lambda: new_id("mission"))
    enterpriseId: str
    title: str
    objective: str
    vendorId: str
    status: MissionStatus = MissionStatus.created
    tasks: list[MissionTask] = Field(default_factory=list)
    plan: list[MissionPlanStep] = Field(default_factory=list)
    planSource: PlanSource = PlanSource.deterministic_fallback
    planModel: str | None = None
    planNotes: str | None = None
    agentStates: dict[str, RuntimeStatus] = Field(default_factory=dict)
    # Derived counter (number of finished tasks). Kept for the existing UI
    # contract; the graph in `tasks` is the execution source of truth.
    currentStep: int = 0
    awaitingApprovalId: str | None = None
    degraded: dict[str, str] = Field(default_factory=dict)
    createdAt: datetime = Field(default_factory=utc_now)
    updatedAt: datetime = Field(default_factory=utc_now)
    completedAt: datetime | None = None
    results: dict[str, Any] = Field(default_factory=dict)

    def task_by_id(self, task_id: str) -> MissionTask | None:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None


class Approval(BaseModel):
    id: str = Field(default_factory=lambda: new_id("appr"))
    missionId: str
    agentId: str
    tool: str
    request: dict[str, Any]
    risk: str = "HIGH"
    reason: str
    policyId: str
    taskId: str | None = None
    status: ApprovalStatus = ApprovalStatus.pending
    createdAt: datetime = Field(default_factory=utc_now)
    decidedAt: datetime | None = None
    decidedBy: str | None = None
    decision: ApprovalStatus | None = None


class PolicyDecision(BaseModel):
    outcome: PolicyOutcome
    agentId: str
    tool: str
    capability: str
    reason: str
    policyId: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class StartMissionRequest(BaseModel):
    """Defaults come from configuration — no brand names are hard-coded here."""

    enterpriseId: str = Field(default_factory=lambda: settings.enterprise_id)
    title: str = Field(default_factory=lambda: f"{settings.default_vendor_name} Vendor Onboarding")
    objective: str = Field(
        default_factory=lambda: (
            f"Evaluate {settings.default_vendor_name} as a strategic supplier for "
            f"{settings.enterprise_name}: verify the company, clear compliance and "
            "sanctions, assess financial risk, set up payment terms, and prepare a "
            "procurement onboarding package if the vendor is compliant."
        )
    )
    vendorId: str = Field(default_factory=lambda: settings.default_vendor_id)


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["granted", "denied"]
    decidedBy: str = "operator"


# ── Enterprise / capability reporting ───────────────────────────────────────


class DepartmentLocation(BaseModel):
    floor: int = 1
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0


class DepartmentTheme(BaseModel):
    primary: str = "#0F1E3D"
    accent: str = "#D4AF37"


class DepartmentCard(BaseModel):
    id: str
    name: str
    description: str = ""
    managerAgentId: str | None = None
    theme: DepartmentTheme = Field(default_factory=DepartmentTheme)
    location: DepartmentLocation = Field(default_factory=DepartmentLocation)
    agentCount: int = 0


class EnterpriseCounts(BaseModel):
    agentsTotal: int = 0
    # Deployable agents (roster status `approved`). Distinct from `agentsBusy`,
    # which counts agents actually executing work right now.
    agentsOnline: int = 0
    agentsBusy: int = 0
    missionsTotal: int = 0
    missionsActive: int = 0
    approvalsPending: int = 0
    securityAlerts: int = 0
    departments: int = 0


class CapabilityReport(BaseModel):
    """Honest per-capability truth for /api/health. `true` only when the code
    path has been proven reachable in this process."""

    gemini: bool = False
    adk: bool = False
    firestore: bool = False
    details: dict[str, str] = Field(default_factory=dict)


class EnterpriseSummary(BaseModel):
    id: str
    name: str
    environment: str
    demoMode: bool
    defaultVendorId: str
    defaultVendorName: str
    departments: list[DepartmentCard] = Field(default_factory=list)
    counts: EnterpriseCounts = Field(default_factory=EnterpriseCounts)
    capabilities: CapabilityReport = Field(default_factory=CapabilityReport)
    storeBackend: str = "memory"
