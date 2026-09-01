"""Mission planner.

Turns an operator's natural-language objective into a validated mission graph.

Order of preference:
  1. Gemini via the `google-genai` SDK, JSON mode + response schema, bounded to
     one call plus at most one retry, with a timeout.
  2. A deterministic, objective-seeded fallback graph.

The distinction is reported honestly: `PlannerResult.source` is `gemini` only
when a Gemini response was received *and* passed `plan_graph.validate_plan`.
Model output never reaches the execution path unvalidated.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any

from nexus_api.core.config import settings
from nexus_api.core.logging import get_logger
from nexus_api.schemas.domain import (
    AgentCard,
    EventType,
    MissionTask,
    PlanSource,
)
from nexus_api.services.capabilities import capabilities
from nexus_api.services.events import event_bus
from nexus_api.services.plan_graph import (
    PlanValidationError,
    topological_layers,
    validate_plan,
)
from nexus_api.services.storage import store

logger = get_logger("planner")

# Tools the platform actually implements (see services/tools.py::_dispatch_tool).
IMPLEMENTED_TOOLS: set[str] = {
    "company_search",
    "company_profile",
    "document_search",
    "policy_search",
    "compliance_check",
    "sanctions_check",
    "financial_lookup",
    "risk_calculator",
    "invoice_analysis",
    "create_payment",
    "supplier_score",
    "contract_generator",
    "contract_finalize",
}

PLANNER_SYSTEM_INSTRUCTION = """\
You are the mission planner for NEXUS, a governed autonomous-enterprise platform.
You convert an operator objective into a directed acyclic graph of tasks.

Hard rules:
- Use ONLY agentId values from the provided roster.
- Assign a task ONLY tools that the chosen agent owns in the roster.
- dependsOn must reference ids of other tasks in the same plan. No cycles.
- Maximise parallelism: tasks that do not need each other's output MUST NOT
  depend on each other.
- Prefer 3 to 6 tasks. Never exceed the stated maximum.
- Return JSON only. No prose, no markdown fences.
"""

PLAN_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "tasks": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"},
                    "title": {"type": "STRING"},
                    "agentId": {"type": "STRING"},
                    "dependsOn": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "tools": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["id", "title", "agentId", "dependsOn", "tools"],
                "propertyOrdering": ["id", "title", "agentId", "dependsOn", "tools"],
            },
        }
    },
    "required": ["tasks"],
}


@dataclass
class PlannerResult:
    tasks: list[MissionTask]
    source: PlanSource
    model: str | None
    notes: str
    layers: list[list[str]] = field(default_factory=list)

    @property
    def is_gemini(self) -> bool:
        return self.source == PlanSource.gemini


class GeminiUnavailableError(RuntimeError):
    """Raised when no Gemini call can be attempted (no SDK / no credentials)."""


# ── SDK availability ────────────────────────────────────────────────────────


def gemini_sdk_status() -> tuple[bool, str]:
    """(installed, human-readable note). Never raises."""
    try:
        from google import genai  # noqa: F401
    except ImportError as exc:
        return False, f"google-genai not importable: {exc}"
    return True, "google-genai importable"


def _build_client() -> Any:
    """Construct a `google.genai.Client`. Raises GeminiUnavailableError when the
    SDK is missing or no credentials are configured."""
    if not settings.enable_gemini_planner:
        raise GeminiUnavailableError("gemini planner disabled by configuration")

    try:
        from google import genai
    except ImportError as exc:
        raise GeminiUnavailableError(f"google-genai not installed: {exc}") from exc

    api_key = settings.resolved_gemini_api_key
    if settings.google_genai_use_vertexai:
        return genai.Client(
            vertexai=True,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
    if not api_key:
        raise GeminiUnavailableError("no GEMINI_API_KEY/GOOGLE_API_KEY configured")
    return genai.Client(api_key=api_key)


# ── Prompt construction ─────────────────────────────────────────────────────


def roster_context(roster: dict[str, AgentCard]) -> list[dict[str, Any]]:
    """The real roster, trimmed to what the planner needs to choose an owner."""
    context: list[dict[str, Any]] = []
    for agent in sorted(roster.values(), key=lambda a: (a.tier.value, a.id)):
        usable = [tool for tool in agent.tools if tool in IMPLEMENTED_TOOLS]
        if not usable:
            # An agent with no executable tool cannot own a task in this runtime.
            continue
        context.append(
            {
                "agentId": agent.id,
                "name": agent.name,
                "role": agent.role,
                "departmentId": agent.departmentId,
                "tier": agent.tier.value,
                "capabilities": agent.capabilities,
                "tools": usable,
            }
        )
    return context


def build_prompt(objective: str, vendor_id: str, roster: dict[str, AgentCard]) -> str:
    payload = {
        "enterprise": {"id": settings.enterprise_id, "name": settings.enterprise_name},
        "objective": objective,
        "subjectVendorId": vendor_id,
        "maxTasks": settings.planner_max_tasks,
        "roster": roster_context(roster),
    }
    return (
        "Plan the following enterprise mission.\n\n"
        f"{json.dumps(payload, indent=2)}\n\n"
        'Respond with JSON of the form {"tasks": [{"id": "...", "title": "...", '
        '"agentId": "...", "dependsOn": [], "tools": []}]}.'
    )


# ── Gemini call ─────────────────────────────────────────────────────────────


def _generate_sync(client: Any, prompt: str) -> str:
    """One blocking generate_content call. Returns raw response text."""
    config: Any
    try:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=PLANNER_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=PLAN_RESPONSE_SCHEMA,
            temperature=0.2,
            max_output_tokens=4096,
        )
    except ImportError:  # pragma: no cover - SDK present but types missing
        config = {
            "response_mime_type": "application/json",
            "response_schema": PLAN_RESPONSE_SCHEMA,
            "temperature": 0.2,
        }

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=config,
    )
    text = getattr(response, "text", None)
    if not text:
        raise ValueError("gemini returned an empty response")
    return text


async def _generate(client: Any, prompt: str) -> str:
    """Prefer the SDK's async surface; fall back to a worker thread."""
    aio = getattr(client, "aio", None)
    if aio is not None and hasattr(aio, "models"):
        try:
            from google.genai import types

            config: Any = types.GenerateContentConfig(
                system_instruction=PLANNER_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=PLAN_RESPONSE_SCHEMA,
                temperature=0.2,
                max_output_tokens=4096,
            )
        except ImportError:  # pragma: no cover
            config = {"response_mime_type": "application/json"}
        response = await aio.models.generate_content(
            model=settings.gemini_model, contents=prompt, config=config
        )
        text = getattr(response, "text", None)
        if not text:
            raise ValueError("gemini returned an empty response")
        return text
    return await asyncio.to_thread(_generate_sync, client, prompt)


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def parse_plan_payload(text: str) -> Any:
    """Extract the `tasks` list from a model response. Tolerates code fences and
    a bare top-level array, but nothing else — anything odd raises."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise PlanValidationError([f"model response is not valid JSON: {exc}"]) from exc
    if isinstance(payload, dict):
        payload = payload.get("tasks")
    if not isinstance(payload, list):
        raise PlanValidationError(["model response has no `tasks` array"])
    return payload


# ── Deterministic fallback ──────────────────────────────────────────────────

_STAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "research": ("research", "verify", "profile", "background", "investigate", "diligence", "document"),
    "compliance": ("complian", "sanction", "legal", "policy", "regulat", "kyc", "audit"),
    "finance": ("financ", "payment", "pay ", "risk", "credit", "budget", "cost", "invoice", "treasury"),
    "procurement": ("procure", "contract", "onboard", "supplier", "vendor", "sourcing", "terms"),
}

_STAGE_SPEC: dict[str, dict[str, Any]] = {
    "research": {
        "agentId": "elena-rao",
        "title": "Verify the vendor and build a company profile",
        "tools": ["company_search", "company_profile", "document_search"],
        "after": [],
    },
    "compliance": {
        "agentId": "marcus-chen",
        "title": "Clear sanctions and assess compliance posture",
        "tools": ["sanctions_check", "compliance_check"],
        "after": ["research"],
    },
    "finance": {
        "agentId": "david-brooks",
        "title": "Assess financial risk and configure payment terms",
        "tools": ["financial_lookup", "risk_calculator", "create_payment"],
        "after": ["research"],
    },
    "procurement": {
        "agentId": "sarah-patel",
        "title": "Score the supplier and draft the onboarding package",
        "tools": ["supplier_score", "contract_generator"],
        "after": ["compliance", "finance"],
    },
}

_STAGE_ORDER = ("research", "compliance", "finance", "procurement")


def _selected_stages(objective: str) -> list[str]:
    text = (objective or "").lower()
    hits = [
        stage
        for stage in _STAGE_ORDER
        if any(keyword in text for keyword in _STAGE_KEYWORDS[stage])
    ]
    if not hits:
        # Nothing recognisable in the objective: run the full governed pipeline.
        return list(_STAGE_ORDER)
    if "research" not in hits:
        # Every downstream stage needs the vendor profile first.
        hits.insert(0, "research")
    if "procurement" in hits and ("compliance" not in hits or "finance" not in hits):
        # Onboarding is inherently governed: the payment-setup step must be
        # planned so the approval gate is part of the demonstrated flow (§38),
        # never skipped because the objective text lacked finance keywords.
        hits.append("compliance")
        hits.append("finance")
    return [stage for stage in _STAGE_ORDER if stage in hits]


def deterministic_plan(
    objective: str,
    vendor_id: str,
    roster: dict[str, AgentCard],
) -> list[MissionTask]:
    """Seeded fallback graph. Deliberately diamond-shaped (compliance and
    finance are siblings) so independent work really does run concurrently."""
    stages = _selected_stages(objective)
    raw: list[dict[str, Any]] = []

    for stage in stages:
        spec = _STAGE_SPEC[stage]
        agent = roster.get(str(spec["agentId"]))
        if agent is None:
            continue
        tools = [tool for tool in spec["tools"] if tool in agent.tools and tool in IMPLEMENTED_TOOLS]
        depends = [f"task-{parent}" for parent in spec["after"] if parent in stages]
        raw.append(
            {
                "id": f"task-{stage}",
                "title": str(spec["title"]),
                "agentId": agent.id,
                "dependsOn": depends,
                "tools": tools,
                "toolArgs": _default_tool_args(tools, vendor_id),
            }
        )

    if not raw:
        raise PlanValidationError(["no roster agent can execute the deterministic fallback plan"])

    return validate_plan(
        raw,
        roster,
        known_tools=IMPLEMENTED_TOOLS,
        max_tasks=settings.planner_max_tasks,
        max_attempts=settings.agent_max_attempts,
    )


def _default_tool_args(tools: list[str], vendor_id: str) -> dict[str, dict[str, Any]]:
    args: dict[str, dict[str, Any]] = {}
    if "create_payment" in tools:
        # Above the finance policy threshold on purpose: this is the governance
        # demo — it must hit REQUIRE_APPROVAL, not slip through.
        args["create_payment"] = {
            "vendorId": vendor_id,
            "recipient": vendor_id,
            "amount": 500000,
            "currency": "INR",
            "reason": "Initial vendor payment setup",
        }
    if "contract_generator" in tools:
        args["contract_generator"] = {
            "vendorId": vendor_id,
            "terms": "Net 60, standard SLA, termination clause",
        }
    return args


# ── Public entry point ──────────────────────────────────────────────────────


class MissionPlanner:
    async def plan(
        self,
        mission_id: str,
        objective: str,
        vendor_id: str,
        roster: dict[str, AgentCard] | None = None,
    ) -> PlannerResult:
        roster = roster or dict(store.agents)
        if not roster:
            roster = {agent.id: agent for agent in store.seed_agents_from_roster()}

        try:
            result = await self._plan_with_gemini(mission_id, objective, vendor_id, roster)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - planning must never kill the runner
            logger.error(
                "planner.gemini_path_crashed",
                missionId=mission_id,
                reason=f"{type(exc).__name__}: {exc}",
            )
            capabilities.record_failure("gemini", f"crashed: {exc}")
            result = None
        if result is None:
            result = self._plan_deterministically(objective, vendor_id, roster)

        result.layers = topological_layers(result.tasks)
        self._emit_plan_created(mission_id, result, objective)
        return result

    async def _plan_with_gemini(
        self,
        mission_id: str,
        objective: str,
        vendor_id: str,
        roster: dict[str, AgentCard],
    ) -> PlannerResult | None:
        try:
            client = _build_client()
        except GeminiUnavailableError as exc:
            logger.warning(
                "planner.gemini_unavailable", missionId=mission_id, reason=str(exc)
            )
            capabilities.record_failure("gemini", f"unavailable: {exc}")
            return None

        prompt = build_prompt(objective, vendor_id, roster)
        attempts = max(1, settings.planner_max_attempts)
        last_error = ""

        for attempt in range(1, attempts + 1):
            try:
                text = await asyncio.wait_for(
                    _generate(client, prompt), timeout=settings.planner_timeout_seconds
                )
                raw_tasks = parse_plan_payload(text)
                tasks = validate_plan(
                    raw_tasks,
                    roster,
                    known_tools=IMPLEMENTED_TOOLS,
                    max_tasks=settings.planner_max_tasks,
                    max_attempts=settings.agent_max_attempts,
                )
            except asyncio.TimeoutError:
                last_error = f"timeout after {settings.planner_timeout_seconds}s"
            except PlanValidationError as exc:
                last_error = f"model output rejected: {'; '.join(exc.reasons)}"
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - SDK errors (google.genai,
                # google.api_core) are subclasses of neither ValueError nor
                # OSError; an uncaught one killed the runner and froze the
                # mission in planning instead of degrading to the fallback.
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                for task in tasks:
                    if not task.toolArgs:
                        task.toolArgs = _default_tool_args(task.tools, vendor_id)
                logger.info(
                    "planner.gemini_plan_accepted",
                    missionId=mission_id,
                    model=settings.gemini_model,
                    attempt=attempt,
                    taskCount=len(tasks),
                )
                capabilities.record_success(
                    "gemini", f"planned mission {mission_id} with {settings.gemini_model}"
                )
                return PlannerResult(
                    tasks=tasks,
                    source=PlanSource.gemini,
                    model=settings.gemini_model,
                    notes=f"Gemini ({settings.gemini_model}) produced a validated {len(tasks)}-task graph.",
                )

            logger.warning(
                "planner.gemini_attempt_failed",
                missionId=mission_id,
                attempt=attempt,
                attempts=attempts,
                reason=last_error,
            )

        capabilities.record_failure("gemini", f"planning failed: {last_error}")
        logger.error(
            "planner.gemini_failed", missionId=mission_id, reason=last_error, attempts=attempts
        )
        return None

    def _plan_deterministically(
        self, objective: str, vendor_id: str, roster: dict[str, AgentCard]
    ) -> PlannerResult:
        tasks = deterministic_plan(objective, vendor_id, roster)
        return PlannerResult(
            tasks=tasks,
            source=PlanSource.deterministic_fallback,
            model=None,
            notes=(
                "Gemini was not used. This plan came from the deterministic, "
                "objective-seeded fallback planner."
            ),
        )

    def _emit_plan_created(self, mission_id: str, result: PlannerResult, objective: str) -> None:
        event_bus.emit(
            EventType.plan_created,
            mission_id,
            (
                f"Plan created from objective ({result.source.value}): "
                f"{len(result.tasks)} tasks, {len(result.layers)} execution layers"
            ),
            "alex-morgan",
            metadata={
                "planSource": result.source.value,
                "planModel": result.model,
                "planNotes": result.notes,
                "objective": objective,
                "graph": [task.model_dump(mode="json") for task in result.tasks],
                "layers": result.layers,
            },
        )


mission_planner = MissionPlanner()
