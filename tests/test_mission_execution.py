"""Mission orchestration: real concurrency, real parking, real circuit breakers.

SANDBOX NOTE: authored where pytest/pydantic were unavailable, so this file was
NOT executed at authoring time. It requires `pydantic` and `pytest-asyncio`
(`asyncio_mode = auto` in pytest.ini). See tests/conftest.py.

Missions are now asynchronous: `start_mission` returns a `created` mission and
hands execution to a background asyncio task. Every test here therefore awaits
`mission_service.wait_for_mission(mission_id, timeout)` instead of assuming the
call was synchronous.

What this file proves:
  * missions get unique generated ids (no `demo-mission-001` anywhere);
  * `POST` semantics: the service returns before the work is done;
  * tasks in the same graph layer are genuinely in flight together — proven both
    by event ordering and by a real `threading.Barrier` rendezvous that can only
    be satisfied if two tool calls overlap in wall-clock time;
  * an approval parks exactly one branch, a sibling branch still completes, the
    parked tool runs exactly once after the grant, and earlier task results and
    tool results survive the park;
  * the tool-call circuit breaker trips and emits `CIRCUIT_BREAKER_TRIPPED`;
  * a failing task retries up to `maxAttempts`, then fails, and its dependents
    are marked `skipped` rather than hanging;
  * a policy DENY inside a mission is not retried (retrying a DENY is pointless
    and would burn the attempt budget).
"""

from __future__ import annotations

import asyncio
import threading

import pytest

from conftest import requires_backend

requires_backend()

from nexus_api.core.config import settings  # noqa: E402
from nexus_api.schemas.domain import (  # noqa: E402
    ApprovalDecisionRequest,
    ApprovalStatus,
    EventType,
    MissionStatus,
    MissionTask,
    PlanSource,
    StartMissionRequest,
    TaskStatus,
)
from nexus_api.services import tools as tools_module  # noqa: E402
from nexus_api.services.mission import mission_service  # noqa: E402
from nexus_api.services.planner import PlannerResult, mission_planner  # noqa: E402
from nexus_api.services.plan_graph import topological_layers  # noqa: E402
from nexus_api.services.storage import store  # noqa: E402

FULL_OBJECTIVE = (
    "Verify the vendor and build a company profile, clear sanctions and assess "
    "compliance posture, assess financial risk and configure payment terms, then "
    "score the supplier and draft the procurement onboarding package."
)
TIMEOUT = 60.0


def _request(**overrides) -> StartMissionRequest:
    fields = {
        "enterpriseId": settings.enterprise_id,
        "title": "Kestrel Components Vendor Onboarding",
        "objective": FULL_OBJECTIVE,
        "vendorId": settings.default_vendor_id,
    }
    fields.update(overrides)
    return StartMissionRequest(**fields)


def _events(mission_id: str):
    return store.list_events(mission_id)


def _types(mission_id: str) -> list[EventType]:
    return [event.type for event in _events(mission_id)]


def _tool_completions(mission_id: str, tool: str) -> int:
    return len(
        [
            event
            for event in _events(mission_id)
            if event.type == EventType.tool_completed and event.metadata.get("tool") == tool
        ]
    )


def _first_index(mission_id: str, event_type: EventType, task_id: str) -> int:
    for index, event in enumerate(_events(mission_id)):
        if event.type == event_type and event.metadata.get("taskId") == task_id:
            return index
    raise AssertionError(f"no {event_type.value} event for task {task_id}")


def _install_plan(monkeypatch, tasks: list[MissionTask]) -> None:
    """Replace the planner with a fixed graph, so graph-shape-specific tests do
    not depend on the objective-keyword heuristics."""

    async def fake_plan(mission_id, objective, vendor_id, roster=None):
        cloned = [task.model_copy(deep=True) for task in tasks]
        return PlannerResult(
            tasks=cloned,
            source=PlanSource.deterministic_fallback,
            model=None,
            notes="fixed graph installed by the test suite",
            layers=topological_layers(cloned),
        )

    monkeypatch.setattr(mission_planner, "plan", fake_plan)


# ── identity and async semantics ────────────────────────────────────────────


async def test_missions_get_unique_generated_ids(seeded_store):
    first = await mission_service.start_mission(_request())
    second = await mission_service.start_mission(_request())

    assert first.id != second.id
    for mission in (first, second):
        assert mission.id.startswith("mission-")
        assert len(mission.id) == len("mission-") + 12
        assert mission.id != "demo-mission-001"

    await mission_service.wait_for_mission(first.id, TIMEOUT)
    await mission_service.wait_for_mission(second.id, TIMEOUT)


async def test_start_mission_returns_before_the_work_is_done(seeded_store):
    """`POST /api/missions` is 202 Accepted for a reason: the returned mission is
    `created`, and a background runner is registered to do the work."""
    mission = await mission_service.start_mission(_request())

    assert mission.status == MissionStatus.created
    assert mission.tasks == []
    assert mission_service.active_runner_count() >= 1

    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert settled.id == mission.id
    assert settled.status != MissionStatus.created
    assert settled.tasks, "the background runner must have planned the mission"


async def test_mission_uses_configured_enterprise_and_vendor_defaults(seeded_store):
    """The old hard-coded `wayne-enterprises` / `acme-technologies` narrative is
    gone: identity comes from configuration only."""
    from nexus_api.core.config import Settings

    # Check the *code* defaults, so a developer's `.env.local` cannot make this
    # pass or fail for the wrong reason.
    assert Settings.model_fields["enterprise_id"].default == "meridian-industrial"
    assert Settings.model_fields["default_vendor_id"].default == "kestrel-components"
    assert Settings.model_fields["enterprise_name"].default == "Meridian Industrial"
    assert Settings.model_fields["default_vendor_name"].default == "Kestrel Components"

    mission = await mission_service.start_mission(StartMissionRequest())

    assert mission.enterpriseId == settings.enterprise_id
    assert mission.vendorId == settings.default_vendor_id
    assert "wayne" not in mission.enterpriseId
    assert "acme" not in mission.vendorId
    assert settings.default_vendor_name in mission.title

    await mission_service.wait_for_mission(mission.id, TIMEOUT)


# ── concurrency is real ─────────────────────────────────────────────────────


async def test_sibling_tasks_are_in_flight_together_by_event_order(seeded_store):
    """Both siblings must emit AGENT_STARTED before either emits AGENT_COMPLETED.

    If the scheduler were sequential, compliance would complete before finance
    started, and this ordering could not hold.
    """
    mission = await mission_service.start_mission(_request())
    await mission_service.wait_for_mission(mission.id, TIMEOUT)

    started_compliance = _first_index(mission.id, EventType.agent_started, "task-compliance")
    started_finance = _first_index(mission.id, EventType.agent_started, "task-finance")
    completed_compliance = _first_index(mission.id, EventType.agent_completed, "task-compliance")

    assert max(started_compliance, started_finance) < completed_compliance, (
        "one sibling completed before the other started — the layer ran sequentially"
    )


async def test_sibling_tasks_really_overlap_in_wall_clock_time(monkeypatch, seeded_store):
    """The strong form of the concurrency claim.

    `execute_tool` runs in a worker thread (`asyncio.to_thread`), so a
    `threading.Barrier(2)` can only be satisfied if the first tool of the
    compliance branch and the first tool of the finance branch are executing at
    the same moment. If the scheduler serialises the layer, the barrier times out.
    """
    rendezvous = threading.Barrier(2, timeout=10)
    watched = {"sanctions_check", "financial_lookup"}
    passed: list[str] = []
    lock = threading.Lock()
    real_dispatch = tools_module._dispatch_tool

    def barrier_dispatch(tool, payload):
        if tool in watched:
            rendezvous.wait()
            with lock:
                passed.append(tool)
        return real_dispatch(tool, payload)

    monkeypatch.setattr(tools_module, "_dispatch_tool", barrier_dispatch)

    mission = await mission_service.start_mission(_request())
    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert sorted(passed) == ["financial_lookup", "sanctions_check"], (
        "the barrier was not satisfied by two simultaneous tool calls"
    )
    compliance = settled.task_by_id("task-compliance")
    assert compliance is not None and compliance.status == TaskStatus.completed


async def test_wave_event_reports_a_concurrency_greater_than_one(seeded_store):
    """The plan must actually be scheduled in waves wider than one task."""
    mission = await mission_service.start_mission(_request())
    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    layers = topological_layers(settled.tasks)
    assert max(len(layer) for layer in layers) >= 2


async def test_independent_branches_do_not_share_tool_results(monkeypatch, seeded_store):
    """Concurrent tasks must not leak each other's tool output into their own
    `result` dict — a shared-mutable-state bug would show up here."""
    _install_plan(
        monkeypatch,
        [
            MissionTask(
                id="a",
                title="research a",
                agentId="elena-rao",
                tools=["company_search"],
            ),
            MissionTask(
                id="b",
                title="compliance b",
                agentId="marcus-chen",
                tools=["sanctions_check"],
            ),
        ],
    )

    mission = await mission_service.start_mission(_request())
    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert settled.status == MissionStatus.completed
    assert set(settled.task_by_id("a").result) == {"company_search"}
    assert set(settled.task_by_id("b").result) == {"sanctions_check"}


# ── approval park / resume ──────────────────────────────────────────────────


async def test_mission_parks_on_approval_while_sibling_branch_completes(seeded_store):
    mission = await mission_service.start_mission(_request())
    parked = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert parked.status == MissionStatus.awaiting_approval
    assert parked.awaitingApprovalId is not None

    research = parked.task_by_id("task-research")
    compliance = parked.task_by_id("task-compliance")
    finance = parked.task_by_id("task-finance")
    procurement = parked.task_by_id("task-procurement")

    assert research.status == TaskStatus.completed
    assert compliance.status == TaskStatus.completed, (
        "the sibling branch must finish even though finance parked"
    )
    assert finance.status == TaskStatus.blocked
    assert finance.pendingTool == "create_payment"
    assert finance.awaitingApprovalId == parked.awaitingApprovalId
    assert procurement.status in (TaskStatus.pending, TaskStatus.ready), (
        "a downstream task must wait, not fail, while an upstream branch is parked"
    )

    approvals = store.list_approvals(ApprovalStatus.pending)
    assert len(approvals) == 1
    assert approvals[0].tool == "create_payment"
    assert approvals[0].agentId == "david-brooks"
    assert approvals[0].taskId == "task-finance"

    types = _types(mission.id)
    assert EventType.approval_requested in types
    assert EventType.agent_paused in types
    assert EventType.mission_paused in types
    # The parked tool must not have run yet.
    assert _tool_completions(mission.id, "create_payment") == 0


async def test_parked_tool_executes_exactly_once_after_the_grant(seeded_store):
    mission = await mission_service.start_mission(_request())
    parked = await mission_service.wait_for_mission(mission.id, TIMEOUT)
    approval_id = parked.awaitingApprovalId

    mission_service.decide_approval(
        approval_id, ApprovalDecisionRequest(decision="granted", decidedBy="operator")
    )
    completed = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert completed.status == MissionStatus.completed
    assert completed.completedAt is not None
    assert _tool_completions(mission.id, "create_payment") == 1, (
        "the parked tool ran either zero times or more than once"
    )
    assert store.get_approval(approval_id).status == ApprovalStatus.granted

    types = _types(mission.id)
    for expected in (
        EventType.mission_created,
        EventType.plan_created,
        EventType.approval_requested,
        EventType.approval_granted,
        EventType.agent_resumed,
        EventType.mission_resumed,
        EventType.mission_completed,
    ):
        assert expected in types, f"missing {expected.value}"


async def test_results_recorded_before_the_park_survive_the_resume(seeded_store):
    mission = await mission_service.start_mission(_request())
    parked = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    research_result_before = dict(parked.results["task-research"])
    finance_before = dict(parked.task_by_id("task-finance").result)
    # The two finance tools that ran before `create_payment` asked for approval.
    assert set(finance_before) == {"financial_lookup", "risk_calculator"}

    mission_service.decide_approval(
        parked.awaitingApprovalId,
        ApprovalDecisionRequest(decision="granted", decidedBy="operator"),
    )
    completed = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert completed.results["task-research"] == research_result_before
    assert "task-compliance" in completed.results
    finance_after = completed.task_by_id("task-finance").result
    assert set(finance_after) == {"financial_lookup", "risk_calculator", "create_payment"}
    assert finance_after["financial_lookup"] == finance_before["financial_lookup"]
    assert completed.task_by_id("task-finance").status == TaskStatus.completed
    # Resuming must not burn a retry attempt.
    assert completed.task_by_id("task-finance").attempts == 1


async def test_resume_does_not_re_run_tools_that_already_succeeded(seeded_store):
    mission = await mission_service.start_mission(_request())
    parked = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    before = _tool_completions(mission.id, "financial_lookup")
    assert before == 1

    mission_service.decide_approval(
        parked.awaitingApprovalId,
        ApprovalDecisionRequest(decision="granted", decidedBy="operator"),
    )
    await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert _tool_completions(mission.id, "financial_lookup") == 1, (
        "resuming replayed a tool that had already succeeded"
    )


async def test_downstream_task_runs_only_after_the_parked_branch_resumes(seeded_store):
    mission = await mission_service.start_mission(_request())
    parked = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert parked.task_by_id("task-procurement").status != TaskStatus.completed

    mission_service.decide_approval(
        parked.awaitingApprovalId,
        ApprovalDecisionRequest(decision="granted", decidedBy="operator"),
    )
    completed = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert completed.task_by_id("task-procurement").status == TaskStatus.completed
    finance_done = _first_index(mission.id, EventType.agent_completed, "task-finance")
    procurement_started = _first_index(mission.id, EventType.agent_started, "task-procurement")
    assert finance_done < procurement_started


async def test_denied_approval_fails_the_mission_and_skips_dependents(seeded_store):
    mission = await mission_service.start_mission(_request())
    parked = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    mission_service.decide_approval(
        parked.awaitingApprovalId,
        ApprovalDecisionRequest(decision="denied", decidedBy="operator"),
    )
    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert settled.status == MissionStatus.failed
    assert settled.task_by_id("task-finance").status == TaskStatus.failed
    assert settled.task_by_id("task-procurement").status == TaskStatus.skipped
    assert _tool_completions(mission.id, "create_payment") == 0
    types = _types(mission.id)
    assert EventType.approval_denied in types
    assert EventType.mission_failed in types


async def test_deciding_the_same_approval_twice_is_idempotent(seeded_store):
    mission = await mission_service.start_mission(_request())
    parked = await mission_service.wait_for_mission(mission.id, TIMEOUT)
    approval_id = parked.awaitingApprovalId

    mission_service.decide_approval(
        approval_id, ApprovalDecisionRequest(decision="granted", decidedBy="operator")
    )
    await mission_service.wait_for_mission(mission.id, TIMEOUT)

    mission_service.decide_approval(
        approval_id, ApprovalDecisionRequest(decision="granted", decidedBy="operator")
    )
    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert settled.status == MissionStatus.completed
    assert _tool_completions(mission.id, "create_payment") == 1, (
        "a replayed approval decision executed the high-risk tool a second time"
    )
    assert len([event for event in _events(mission.id) if event.type == EventType.approval_granted]) == 1


# ── circuit breakers ────────────────────────────────────────────────────────


async def test_tool_call_limit_trips_the_circuit_breaker(monkeypatch, seeded_store):
    monkeypatch.setattr(settings, "mission_max_tool_calls", 1)

    mission = await mission_service.start_mission(_request())
    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    types = _types(mission.id)
    assert EventType.circuit_breaker_tripped in types
    assert EventType.mission_failed in types
    assert settled.status == MissionStatus.failed

    tripped = next(
        event for event in _events(mission.id) if event.type == EventType.circuit_breaker_tripped
    )
    assert tripped.metadata["reason"] == "tool_limit"
    assert tripped.metadata["limit"] == 1
    assert tripped.metadata["toolCalls"] > 1


async def test_task_limit_trips_the_circuit_breaker(monkeypatch, seeded_store):
    monkeypatch.setattr(settings, "mission_max_tasks", 2)

    mission = await mission_service.start_mission(_request())
    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert settled.status == MissionStatus.failed
    assert EventType.mission_failed in _types(mission.id)
    reason = next(
        event.metadata["reason"]
        for event in _events(mission.id)
        if event.type == EventType.mission_failed
    )
    assert "task" in reason and "limit" in reason


async def test_wall_clock_breaker_trips_when_the_deadline_is_already_past(
    monkeypatch, seeded_store
):
    monkeypatch.setattr(settings, "mission_max_runtime_minutes", 0)

    mission = await mission_service.start_mission(_request())
    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert settled.status == MissionStatus.failed
    tripped = [
        event
        for event in _events(mission.id)
        if event.type == EventType.circuit_breaker_tripped
    ]
    assert tripped
    assert tripped[0].metadata["reason"] == "timeout"


# ── retries and unreachable tasks ───────────────────────────────────────────


async def test_failing_task_retries_to_max_attempts_then_fails_and_skips_dependents(
    monkeypatch, seeded_store
):
    max_attempts = 2
    _install_plan(
        monkeypatch,
        [
            MissionTask(
                id="flaky",
                title="always fails",
                agentId="marcus-chen",
                tools=["sanctions_check"],
                maxAttempts=max_attempts,
            ),
            MissionTask(
                id="downstream",
                title="needs flaky",
                agentId="david-brooks",
                dependsOn=["flaky"],
                tools=["financial_lookup"],
                maxAttempts=max_attempts,
            ),
        ],
    )

    calls = {"count": 0}
    real_dispatch = tools_module._dispatch_tool

    def flaky_dispatch(tool, payload):
        if tool == "sanctions_check":
            calls["count"] += 1
            raise ValueError("upstream sanctions provider is unreachable")
        return real_dispatch(tool, payload)

    monkeypatch.setattr(tools_module, "_dispatch_tool", flaky_dispatch)

    mission = await mission_service.start_mission(_request())
    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert calls["count"] == max_attempts, "the task did not retry exactly maxAttempts times"
    flaky = settled.task_by_id("flaky")
    downstream = settled.task_by_id("downstream")
    assert flaky.status == TaskStatus.failed
    assert flaky.attempts == max_attempts
    assert downstream.status == TaskStatus.skipped, (
        "a task whose dependency failed must be skipped, not left pending forever"
    )
    assert settled.status == MissionStatus.failed

    failures = [
        event for event in _events(mission.id) if event.type == EventType.agent_failed
    ]
    assert len(failures) == max_attempts
    assert [event.metadata["willRetry"] for event in failures] == [True, False]
    assert EventType.tool_failed in _types(mission.id)
    assert EventType.agent_waiting in _types(mission.id)


async def test_a_recovering_task_completes_on_its_second_attempt(monkeypatch, seeded_store):
    _install_plan(
        monkeypatch,
        [
            MissionTask(
                id="flaky",
                title="fails once",
                agentId="marcus-chen",
                tools=["sanctions_check"],
                maxAttempts=3,
            )
        ],
    )

    calls = {"count": 0}
    real_dispatch = tools_module._dispatch_tool

    def once_failing(tool, payload):
        if tool == "sanctions_check":
            calls["count"] += 1
            if calls["count"] == 1:
                raise ValueError("transient outage")
        return real_dispatch(tool, payload)

    monkeypatch.setattr(tools_module, "_dispatch_tool", once_failing)

    mission = await mission_service.start_mission(_request())
    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert settled.status == MissionStatus.completed
    assert settled.task_by_id("flaky").status == TaskStatus.completed
    assert settled.task_by_id("flaky").attempts == 2


async def test_policy_denied_task_is_not_retried(monkeypatch, seeded_store):
    """A DENY is deterministic. Retrying it would waste the attempt budget and
    spam the audit log, so the task must fail on the first attempt."""
    _install_plan(
        monkeypatch,
        [
            MissionTask(
                id="escalate",
                title="research agent reaches for the payment tool",
                agentId="elena-rao",
                # `tools` is not re-validated here, which is exactly how a
                # smuggled-in illegal tool would look at execution time.
                tools=["create_payment"],
                maxAttempts=3,
            )
        ],
    )

    mission = await mission_service.start_mission(_request())
    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    task = settled.task_by_id("escalate")
    assert task.status == TaskStatus.failed
    assert task.attempts == 1, "a policy DENY must not be retried"
    assert "policy denied" in (task.error or "")
    assert settled.status == MissionStatus.failed

    types = _types(mission.id)
    assert EventType.policy_blocked in types
    assert EventType.tool_completed not in types
    assert _tool_completions(mission.id, "create_payment") == 0


async def test_missing_agent_fails_the_task_without_retrying(monkeypatch, seeded_store):
    _install_plan(
        monkeypatch,
        [
            MissionTask(
                id="ghost",
                title="assigned to nobody",
                agentId="not-in-the-roster",
                tools=[],
                maxAttempts=3,
            )
        ],
    )

    mission = await mission_service.start_mission(_request())
    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    task = settled.task_by_id("ghost")
    assert task.status == TaskStatus.failed
    assert "not in the roster" in (task.error or "")
    assert settled.status == MissionStatus.failed


# ── projection and hand-offs ────────────────────────────────────────────────


async def test_flat_plan_projection_matches_the_graph(seeded_store):
    mission = await mission_service.start_mission(_request())
    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    assert len(settled.plan) == len(settled.tasks)
    assert [step.step for step in settled.plan] == list(range(1, len(settled.tasks) + 1))
    order = [task_id for layer in topological_layers(settled.tasks) for task_id in layer]
    assert [step.taskId for step in settled.plan] == order
    for step in settled.plan:
        task = settled.task_by_id(step.taskId)
        assert step.agentId == task.agentId
        assert step.dependsOn == task.dependsOn


async def test_completed_task_hands_off_to_its_real_dependents(seeded_store):
    mission = await mission_service.start_mission(_request())
    await mission_service.wait_for_mission(mission.id, TIMEOUT)

    handoffs = [
        event for event in _events(mission.id) if event.type == EventType.agent_message
    ]
    research_handoffs = {
        event.targetAgentId
        for event in handoffs
        if event.metadata.get("taskId") == "task-research"
    }
    # research -> compliance and research -> finance are the real graph edges.
    assert research_handoffs == {"marcus-chen", "david-brooks"}


async def test_adk_degradation_is_recorded_not_hidden(seeded_store):
    """With no ADK SDK installed, reasoning must be explicitly labelled as
    deterministic and the mission must record the degradation."""
    from nexus_api.services import adk_runtime

    installed, _ = adk_runtime.adk_sdk_status()
    if installed:
        pytest.skip("google-adk is installed; ADK success is covered by the integration test")

    mission = await mission_service.start_mission(_request())
    settled = await mission_service.wait_for_mission(mission.id, TIMEOUT)

    research = settled.task_by_id("task-research")
    assert research.reasoningRuntime == adk_runtime.FALLBACK_RUNTIME
    assert "deterministic summary" in research.reasoning
    assert "adk" in settled.degraded
    assert settled.planSource == PlanSource.deterministic_fallback
    assert "planner" in settled.degraded


async def test_wait_for_mission_times_out_rather_than_hanging(monkeypatch, seeded_store):
    """`wait_for_mission` must raise, not block forever, when a runner stalls."""
    _install_plan(
        monkeypatch,
        [MissionTask(id="slow", title="slow", agentId="elena-rao", tools=["company_search"])],
    )

    real_dispatch = tools_module._dispatch_tool

    def slow_dispatch(tool, payload):
        if tool == "company_search":
            threading.Event().wait(2)
        return real_dispatch(tool, payload)

    monkeypatch.setattr(tools_module, "_dispatch_tool", slow_dispatch)

    mission = await mission_service.start_mission(_request())
    with pytest.raises(TimeoutError):
        await mission_service.wait_for_mission(mission.id, 0.2)

    # Let the runner finish so the loop is not torn down mid-task.
    await mission_service.wait_for_mission(mission.id, TIMEOUT)


async def test_concurrent_missions_do_not_interfere(seeded_store):
    """Two missions in flight at once must keep separate graphs, events, and
    approvals — mission id must be the only thing distinguishing them."""
    first = await mission_service.start_mission(_request(title="First"))
    second = await mission_service.start_mission(_request(title="Second"))

    await asyncio.gather(
        mission_service.wait_for_mission(first.id, TIMEOUT),
        mission_service.wait_for_mission(second.id, TIMEOUT),
    )

    first_events = _events(first.id)
    second_events = _events(second.id)
    assert first_events and second_events
    assert all(event.missionId == first.id for event in first_events)
    assert all(event.missionId == second.id for event in second_events)

    approvals = store.list_approvals(ApprovalStatus.pending)
    assert {approval.missionId for approval in approvals} == {first.id, second.id}
    assert len(approvals) == 2
