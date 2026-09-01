"""Mission orchestration.

There is no hard-coded plan and no `if agentId == ...` dispatch in this module.
A mission is a graph produced by `services/planner.py`; the orchestrator resolves
which nodes are ready, runs independent nodes **concurrently**, and derives each
node's behaviour purely from data — the task's `tools` list plus the agent's
roster card.

Invariants this module must never break:
  * every tool call goes through `services/tools.py::execute_tool`, so the
    least-privilege policy gate in `services/policy.py` is always applied;
  * an `ApprovalRequiredError` parks exactly one branch and never cancels the
    branches already in flight;
  * execution is bounded: per-task attempts, per-mission tool calls, per-mission
    task count, per-mission wall clock;
  * missions run in a background asyncio task so the HTTP request returns
    immediately (§22 — the backend must not depend on the browser).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nexus_api.core.config import settings
from nexus_api.core.logging import get_logger
from nexus_api.schemas.domain import (
    AgentCard,
    ApprovalDecisionRequest,
    ApprovalStatus,
    EventType,
    Mission,
    MissionPlanStep,
    MissionStatus,
    MissionTask,
    PlanSource,
    RuntimeStatus,
    StartMissionRequest,
    TaskStatus,
    new_id,
    utc_now,
)
from nexus_api.services import adk_runtime, tools as tools_module
from nexus_api.services.events import event_bus
from nexus_api.services.plan_graph import (
    PlanValidationError,
    blocked_by_failure,
    downstream_agents,
    is_terminal,
    ready_tasks,
    topological_layers,
)
from nexus_api.services.planner import mission_planner
from nexus_api.services.policy import ApprovalRequiredError, PolicyViolationError
from nexus_api.services.security import scan_document_for_prompt_injection
from nexus_api.services.storage import DATA_DIR, store

logger = get_logger("mission")

ORCHESTRATOR_AGENT_ID = "alex-morgan"

_TASK_TO_STEP_STATUS: dict[TaskStatus, str] = {
    TaskStatus.pending: "pending",
    TaskStatus.ready: "pending",
    TaskStatus.in_progress: "in_progress",
    TaskStatus.blocked: "blocked",
    TaskStatus.completed: "completed",
    TaskStatus.failed: "failed",
    TaskStatus.skipped: "skipped",
}


class MissionAborted(RuntimeError):
    """Raised internally when a circuit breaker halts the mission."""


@dataclass
class TaskOutcome:
    task_id: str
    status: TaskStatus
    parked: bool = False
    error: str | None = None


class MissionService:
    """Owns mission lifecycle and the background execution loop."""

    def __init__(self) -> None:
        self._runners: dict[str, asyncio.Task[None]] = {}

    # ── demo helpers ────────────────────────────────────────────────────────

    def seed_demo(self) -> dict[str, object]:
        store.reset()
        agents = store.seed_agents_from_roster()
        logger.info("mission.demo_seeded", agents=len(agents))
        return {"status": "seeded", "agents": len(agents)}

    # ── creation ────────────────────────────────────────────────────────────

    def create_mission(self, request: StartMissionRequest) -> Mission:
        """Create and persist a mission. Does not plan and does not execute."""
        if not store.agents:
            store.seed_agents_from_roster()

        mission = Mission(
            id=new_id("mission"),
            enterpriseId=request.enterpriseId,
            title=request.title,
            objective=request.objective,
            vendorId=request.vendorId,
            status=MissionStatus.created,
            agentStates={ORCHESTRATOR_AGENT_ID: RuntimeStatus.idle},
        )
        store.save_mission(mission)
        event_bus.emit(
            EventType.mission_created,
            mission.id,
            f"Mission created: {mission.title}",
            ORCHESTRATOR_AGENT_ID,
            metadata={
                "objective": mission.objective,
                "vendorId": mission.vendorId,
                "enterpriseId": mission.enterpriseId,
            },
        )
        logger.info(
            "mission.created",
            missionId=mission.id,
            enterpriseId=mission.enterpriseId,
            vendorId=mission.vendorId,
        )
        return mission

    async def start_mission(self, request: StartMissionRequest) -> Mission:
        """Create a mission and hand execution to a background task.

        Returns immediately with the `created` mission; the caller watches
        progress over SSE (`/api/events/stream`).
        """
        mission = self.create_mission(request)
        self._spawn(mission.id, self._plan_and_run(mission.id))
        return mission

    # ── background task plumbing ────────────────────────────────────────────

    def _spawn(self, mission_id: str, coro) -> asyncio.Task[None]:  # noqa: ANN001
        """Run `coro` in the background, serialised behind any active runner for
        the same mission so two schedulers never touch one graph at once."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as exc:  # pragma: no cover - misuse guard
            coro.close()
            raise RuntimeError(
                "mission execution requires a running event loop; "
                "call start_mission/decide_approval from async context"
            ) from exc

        previous = self._runners.get(mission_id)
        task = loop.create_task(
            self._chain(mission_id, previous, coro), name=f"mission:{mission_id}"
        )
        self._runners[mission_id] = task
        task.add_done_callback(lambda finished: self._on_runner_done(mission_id, finished))
        return task

    async def _chain(self, mission_id: str, previous: asyncio.Task[None] | None, coro) -> None:  # noqa: ANN001
        if previous is not None and not previous.done():
            logger.info("mission.runner_queued", missionId=mission_id)
            try:
                await asyncio.shield(previous)
            except asyncio.CancelledError:
                raise
            except BaseException as exc:  # noqa: BLE001 - previous errors already logged
                logger.warning(
                    "mission.previous_runner_error",
                    missionId=mission_id,
                    reason=f"{type(exc).__name__}: {exc}",
                )
        await coro

    def _on_runner_done(self, mission_id: str, task: asyncio.Task[None]) -> None:
        if self._runners.get(mission_id) is task:
            self._runners.pop(mission_id, None)
        if task.cancelled():
            logger.warning("mission.runner_cancelled", missionId=mission_id)
            return
        error = task.exception()
        if error is not None:
            logger.error(
                "mission.runner_crashed",
                missionId=mission_id,
                reason=f"{type(error).__name__}: {error}",
            )

    async def wait_for_mission(self, mission_id: str, timeout: float = 30.0) -> Mission:
        """Await the background runner (if any) and return the mission.

        Used by tests and by any caller that wants synchronous semantics.
        """
        deadline = time.monotonic() + timeout
        while True:
            runner = self._runners.get(mission_id)
            if runner is None:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"mission {mission_id} did not settle within {timeout}s")
            try:
                await asyncio.wait_for(asyncio.shield(runner), timeout=remaining)
            except asyncio.TimeoutError as exc:
                raise TimeoutError(
                    f"mission {mission_id} did not settle within {timeout}s"
                ) from exc
        return store.get_mission(mission_id)

    def active_runner_count(self) -> int:
        return len([task for task in self._runners.values() if not task.done()])

    # ── planning + execution ────────────────────────────────────────────────

    async def _plan_and_run(self, mission_id: str) -> None:
        try:
            mission = store.get_mission(mission_id)
        except KeyError:
            logger.warning("mission.vanished_before_plan", missionId=mission_id)
            return

        mission.status = MissionStatus.planning
        mission.agentStates[ORCHESTRATOR_AGENT_ID] = RuntimeStatus.planning
        store.save_mission(mission)

        try:
            result = await mission_planner.plan(
                mission.id, mission.objective, mission.vendorId, dict(store.agents)
            )
        except PlanValidationError as exc:
            self._fail_mission(mission, f"planning failed: {'; '.join(exc.reasons)}")
            return

        if len(result.tasks) > settings.mission_max_tasks:
            self._fail_mission(
                mission,
                f"plan has {len(result.tasks)} tasks, mission limit is {settings.mission_max_tasks}",
            )
            return

        mission.tasks = result.tasks
        mission.planSource = result.source
        mission.planModel = result.model
        mission.planNotes = result.notes
        if result.source == PlanSource.deterministic_fallback:
            mission.degraded["planner"] = result.notes
        mission.agentStates[ORCHESTRATOR_AGENT_ID] = RuntimeStatus.working
        for task in result.tasks:
            mission.agentStates.setdefault(task.agentId, RuntimeStatus.idle)
        mission.status = MissionStatus.running
        self._sync_projection(mission)
        store.save_mission(mission)

        logger.info(
            "mission.plan_ready",
            missionId=mission.id,
            planSource=result.source.value,
            planModel=result.model,
            taskCount=len(result.tasks),
            layers=len(result.layers),
        )

        await self._execute(mission_id)

    async def _execute(self, mission_id: str) -> None:
        """Schedule ready tasks in concurrent waves until done, blocked, or halted."""
        try:
            mission = store.get_mission(mission_id)
        except KeyError:
            logger.warning("mission.vanished_before_execute", missionId=mission_id)
            return

        deadline = time.monotonic() + settings.mission_timeout_seconds
        max_waves = settings.mission_max_tasks * 2 + 5

        for wave in range(max_waves):
            mission = store.get_mission(mission_id)
            if mission.status in (
                MissionStatus.failed,
                MissionStatus.completed,
                MissionStatus.terminated,
            ):
                return
            if self._circuit_breaker_tripped(mission, deadline):
                return

            self._skip_unreachable(mission)
            batch = [
                task
                for task in ready_tasks(mission.tasks)
                if task.awaitingApprovalId is None
            ]
            if not batch:
                break

            for task in batch:
                task.status = TaskStatus.in_progress
            self._sync_projection(mission)
            store.save_mission(mission)

            logger.info(
                "mission.wave_started",
                missionId=mission_id,
                wave=wave,
                concurrency=len(batch),
                tasks=[task.id for task in batch],
            )

            outcomes = await asyncio.gather(
                *[self._run_task(mission_id, task.id) for task in batch],
                return_exceptions=True,
            )

            mission = store.get_mission(mission_id)
            for scheduled, outcome in zip(batch, outcomes):
                if not isinstance(outcome, BaseException):
                    continue
                if isinstance(outcome, asyncio.CancelledError):
                    # Preserve cancellation semantics for the whole runner.
                    raise outcome
                logger.error(
                    "mission.task_runner_crashed",
                    missionId=mission_id,
                    taskId=scheduled.id,
                    reason=f"{type(outcome).__name__}: {outcome}",
                )
                # An unexpected crash must not leave the node stuck in
                # `in_progress`: `_settle` defers while any task is in flight, so
                # a dead runner would otherwise hang the mission forever.
                crashed = mission.task_by_id(scheduled.id)
                if crashed is not None and crashed.status == TaskStatus.in_progress:
                    self._fail_task(
                        mission,
                        crashed,
                        f"task runner crashed: {type(outcome).__name__}: {outcome}",
                    )
            self._sync_projection(mission)
            store.save_mission(mission)

            if any(
                isinstance(outcome, TaskOutcome) and outcome.parked for outcome in outcomes
            ):
                # A branch is parked on human approval. Everything else in this
                # wave has already finished; stop scheduling new work.
                break
        else:
            self._fail_mission(
                store.get_mission(mission_id), f"scheduler exceeded {max_waves} waves"
            )
            return

        self._settle(mission_id)

    def _settle(self, mission_id: str) -> None:
        mission = store.get_mission(mission_id)
        if mission.status in (
            MissionStatus.completed,
            MissionStatus.failed,
            MissionStatus.terminated,
        ):
            self._sync_projection(mission)
            store.save_mission(mission)
            return

        # A task can still be in flight here: the operator may grant an approval
        # while this wave is finishing, which flips the parked task back to
        # `in_progress` and queues a resume runner behind this one. Declaring the
        # mission stuck in that window would fail a mission that is about to make
        # progress, so defer and let the runner that owns the task settle it.
        if any(task.status == TaskStatus.in_progress for task in mission.tasks):
            mission.status = MissionStatus.running
            self._sync_projection(mission)
            store.save_mission(mission)
            logger.info(
                "mission.settle_deferred",
                missionId=mission.id,
                reason="task_in_progress",
                tasks=[
                    task.id for task in mission.tasks if task.status == TaskStatus.in_progress
                ],
            )
            return

        # Parked branches are discovered from the graph rather than from the
        # single `mission.awaitingApprovalId` field, so two independent tasks can
        # await separate approvals in the same wave without the second one being
        # forgotten and the mission being declared unrunnable.
        parked = [task for task in mission.tasks if task.awaitingApprovalId is not None]
        if parked and not is_terminal(mission.tasks):
            mission.awaitingApprovalId = parked[0].awaitingApprovalId
            mission.status = MissionStatus.awaiting_approval
            self._sync_projection(mission)
            store.save_mission(mission)
            event_bus.emit(
                EventType.mission_paused,
                mission.id,
                "Mission paused — operator approval required",
                ORCHESTRATOR_AGENT_ID,
                metadata={
                    "approvalId": mission.awaitingApprovalId,
                    "pendingApprovalIds": [task.awaitingApprovalId for task in parked],
                    "parkedTasks": [task.id for task in parked],
                },
            )
            return

        failed = [task for task in mission.tasks if task.status == TaskStatus.failed]
        if failed:
            self._fail_mission(
                mission,
                f"tasks failed: {', '.join(task.id for task in failed)}",
            )
            return

        if is_terminal(mission.tasks):
            mission.status = MissionStatus.completed
            mission.completedAt = utc_now()
            mission.agentStates[ORCHESTRATOR_AGENT_ID] = RuntimeStatus.completed
            self._sync_projection(mission)
            store.save_mission(mission)
            event_bus.emit(
                EventType.mission_completed,
                mission.id,
                f"Mission completed: {mission.title}",
                ORCHESTRATOR_AGENT_ID,
                metadata={
                    "vendorId": mission.vendorId,
                    "planSource": mission.planSource.value,
                    "tasks": len(mission.tasks),
                },
            )
            logger.info(
                "mission.completed",
                missionId=mission.id,
                planSource=mission.planSource.value,
                tasks=len(mission.tasks),
            )
            return

        # Nothing ready, nothing parked, not terminal: the graph cannot advance.
        self._fail_mission(mission, "no runnable task remains and the mission is not complete")

    # ── one task ────────────────────────────────────────────────────────────

    async def _run_task(
        self,
        mission_id: str,
        task_id: str,
        approved_approval_id: str | None = None,
    ) -> TaskOutcome:
        mission = store.get_mission(mission_id)
        task = mission.task_by_id(task_id)
        if task is None:
            return TaskOutcome(task_id, TaskStatus.failed, error="task not found")

        try:
            agent = store.get_agent(task.agentId)
        except KeyError:
            return self._fail_task(
                mission, task, f"agent {task.agentId} is not in the roster", retryable=False
            )

        resuming = approved_approval_id is not None
        if resuming and task.pendingTool and task.pendingTool in task.tools:
            start_index = task.tools.index(task.pendingTool)
            remaining = task.tools[start_index:]
            tool_results: dict[str, Any] = dict(task.result)
        else:
            remaining = list(task.tools)
            tool_results = {}
            task.attempts += 1

        task.status = TaskStatus.in_progress
        task.startedAt = task.startedAt or utc_now()
        task.error = None
        task.awaitingApprovalId = None
        task.pendingTool = None
        mission.agentStates[agent.id] = RuntimeStatus.working
        store.save_mission(mission)
        event_bus.emit(
            EventType.agent_started,
            mission.id,
            f"{agent.name} started: {task.title}",
            agent.id,
            metadata={
                "taskId": task.id,
                "attempt": task.attempts,
                "maxAttempts": task.maxAttempts,
                "tools": remaining,
            },
        )

        approval_token = approved_approval_id
        for index, tool in enumerate(remaining):
            # Throttle real execution so each wave is observable on the floor
            # (synthetic tools would otherwise complete inside one event tick).
            pacing = settings.task_pacing_seconds
            if pacing > 0:
                await asyncio.sleep(pacing if index == 0 else pacing * 0.4)
            payload = self._tool_payload(task, tool, mission)
            try:
                result = await asyncio.to_thread(
                    tools_module.execute_tool,
                    mission.id,
                    agent.id,
                    tool,
                    payload,
                    approval_token,
                    task.id,
                )
            except ApprovalRequiredError as exc:
                task.result = tool_results
                return self._park_task(mission, task, agent, tool, exc)
            except PolicyViolationError as exc:
                task.result = tool_results
                # A DENY is deterministic: retrying cannot change the outcome, so
                # the task fails immediately instead of burning attempts.
                return self._fail_task(
                    mission, task, f"policy denied {tool}: {exc}", retryable=False
                )
            except (ValueError, KeyError, TypeError, OSError) as exc:
                task.result = tool_results
                event_bus.emit(
                    EventType.tool_failed,
                    mission.id,
                    f"{tool} failed: {exc}",
                    agent.id,
                    metadata={"taskId": task.id, "tool": tool, "error": str(exc)},
                )
                return self._fail_task(
                    mission, task, f"{tool} failed: {type(exc).__name__}: {exc}"
                )
            finally:
                approval_token = None

            tool_results[tool] = result
            self._scan_returned_documents(mission, agent.id, task, result)

        task.result = tool_results

        reasoning = await adk_runtime.run_agent_reasoning(
            agent=agent,
            objective=mission.objective,
            task_title=task.title,
            tool_results=tool_results,
            session_id=f"{mission.id}:{task.id}",
        )
        task.reasoning = reasoning.text
        task.reasoningRuntime = reasoning.runtime
        if reasoning.degraded and reasoning.error:
            mission.degraded["adk"] = reasoning.error

        return self._complete_task(mission, task, agent, tool_results, reasoning)

    def _tool_payload(self, task: MissionTask, tool: str, mission: Mission) -> dict[str, Any]:
        """Arguments for a tool call.

        Explicit `toolArgs` win; otherwise the mission subject is passed under
        both key names the tool layer understands. No agent-specific branching.
        """
        explicit = task.toolArgs.get(tool)
        if explicit:
            return dict(explicit)
        return {"vendorId": mission.vendorId, "companyId": mission.vendorId}

    def _scan_returned_documents(
        self, mission: Mission, agent_id: str, task: MissionTask, result: dict[str, Any]
    ) -> None:
        """Run the prompt-injection scan over any document a tool surfaced.

        Data-driven: triggered by the shape of the tool result, not by which
        agent is running.
        """
        documents = result.get("documents") if isinstance(result, dict) else None
        if not isinstance(documents, list):
            return
        findings: list[dict[str, object]] = []
        for name in documents:
            path = Path(DATA_DIR / "synthetic" / str(name))
            if not path.exists():
                continue
            outcome = scan_document_for_prompt_injection(mission.id, agent_id, path)
            findings.append({"document": str(name), **outcome})
        if findings:
            security = mission.results.setdefault("security", {})
            if isinstance(security, dict):
                security[task.id] = findings

    def _complete_task(
        self,
        mission: Mission,
        task: MissionTask,
        agent: AgentCard,
        tool_results: dict[str, Any],
        reasoning: adk_runtime.AgentReasoning,
    ) -> TaskOutcome:
        task.status = TaskStatus.completed
        task.completedAt = utc_now()
        mission.agentStates[agent.id] = RuntimeStatus.completed
        mission.results[task.id] = {
            "agentId": agent.id,
            "title": task.title,
            "tools": tool_results,
            "reasoning": reasoning.text,
            "reasoningRuntime": reasoning.runtime,
        }

        for target in downstream_agents(mission.tasks, task.id):
            event_bus.emit(
                EventType.agent_message,
                mission.id,
                f"{agent.name} handed off '{task.title}' findings",
                agent.id,
                target,
                metadata={"taskId": task.id, "summary": reasoning.text[:400]},
            )

        event_bus.emit(
            EventType.agent_completed,
            mission.id,
            f"{agent.name} completed: {task.title}",
            agent.id,
            metadata={
                "taskId": task.id,
                "tools": list(tool_results.keys()),
                "reasoningRuntime": reasoning.runtime,
                "degraded": reasoning.degraded,
            },
        )
        self._sync_projection(mission)
        store.save_mission(mission)
        logger.info(
            "mission.task_completed",
            missionId=mission.id,
            taskId=task.id,
            agentId=agent.id,
            reasoningRuntime=reasoning.runtime,
        )
        return TaskOutcome(task.id, TaskStatus.completed)

    def _park_task(
        self,
        mission: Mission,
        task: MissionTask,
        agent: AgentCard,
        tool: str,
        exc: ApprovalRequiredError,
    ) -> TaskOutcome:
        approval_id = exc.approvalId
        if approval_id is None:
            approvals = store.list_approvals(ApprovalStatus.pending)
            approval_id = approvals[-1].id if approvals else None

        task.status = TaskStatus.blocked
        task.awaitingApprovalId = approval_id
        task.pendingTool = tool
        mission.agentStates[agent.id] = RuntimeStatus.approval_required
        mission.awaitingApprovalId = approval_id
        mission.status = MissionStatus.awaiting_approval
        self._sync_projection(mission)
        store.save_mission(mission)

        event_bus.emit(
            EventType.agent_paused,
            mission.id,
            f"{agent.name} paused — operator approval required for {tool}",
            agent.id,
            metadata={"taskId": task.id, "approvalId": approval_id, "tool": tool},
        )
        logger.info(
            "mission.task_parked",
            missionId=mission.id,
            taskId=task.id,
            agentId=agent.id,
            tool=tool,
            approvalId=approval_id,
        )
        return TaskOutcome(task.id, TaskStatus.blocked, parked=True)

    def _fail_task(
        self,
        mission: Mission,
        task: MissionTask,
        reason: str,
        retryable: bool = True,
    ) -> TaskOutcome:
        can_retry = retryable and task.attempts < task.maxAttempts
        task.error = reason
        task.status = TaskStatus.pending if can_retry else TaskStatus.failed
        mission.agentStates[task.agentId] = (
            RuntimeStatus.waiting if can_retry else RuntimeStatus.failed
        )
        self._sync_projection(mission)
        store.save_mission(mission)

        event_bus.emit(
            EventType.agent_failed,
            mission.id,
            f"{task.agentId} failed on '{task.title}': {reason}",
            task.agentId,
            metadata={
                "taskId": task.id,
                "reason": reason,
                "attempt": task.attempts,
                "maxAttempts": task.maxAttempts,
                "willRetry": can_retry,
                "retryable": retryable,
            },
        )
        logger.warning(
            "mission.task_failed",
            missionId=mission.id,
            taskId=task.id,
            agentId=task.agentId,
            reason=reason,
            attempt=task.attempts,
            willRetry=can_retry,
        )
        return TaskOutcome(
            task.id,
            TaskStatus.pending if can_retry else TaskStatus.failed,
            error=reason,
        )

    def _skip_unreachable(self, mission: Mission) -> None:
        for task in blocked_by_failure(mission.tasks):
            task.status = TaskStatus.skipped
            task.error = task.error or "upstream task failed"
            mission.agentStates[task.agentId] = RuntimeStatus.blocked
            event_bus.emit(
                EventType.agent_waiting,
                mission.id,
                f"{task.agentId} cannot start '{task.title}' — upstream task failed",
                task.agentId,
                metadata={"taskId": task.id, "dependsOn": task.dependsOn},
            )

    # ── circuit breakers ────────────────────────────────────────────────────

    def _circuit_breaker_tripped(self, mission: Mission, deadline: float) -> bool:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            self._trip(
                mission,
                "timeout",
                f"Mission exceeded {settings.mission_timeout_seconds:.0f}s wall clock",
                {"timeoutSeconds": settings.mission_timeout_seconds},
            )
            return True

        tool_calls = len(
            [
                event
                for event in store.list_events(mission.id)
                if event.type == EventType.tool_started
            ]
        )
        if tool_calls > settings.mission_max_tool_calls:
            self._trip(
                mission,
                "tool_limit",
                f"Tool call limit exceeded ({tool_calls} > {settings.mission_max_tool_calls})",
                {"toolCalls": tool_calls, "limit": settings.mission_max_tool_calls},
            )
            return True

        if len(mission.tasks) > settings.mission_max_tasks:
            self._trip(
                mission,
                "task_limit",
                f"Task limit exceeded ({len(mission.tasks)} > {settings.mission_max_tasks})",
                {"tasks": len(mission.tasks), "limit": settings.mission_max_tasks},
            )
            return True
        return False

    def _trip(
        self, mission: Mission, reason: str, summary: str, metadata: dict[str, Any]
    ) -> None:
        event_bus.emit(
            EventType.circuit_breaker_tripped,
            mission.id,
            summary,
            ORCHESTRATOR_AGENT_ID,
            metadata={"reason": reason, **metadata},
        )
        logger.error("mission.circuit_breaker", missionId=mission.id, reason=reason)
        self._fail_mission(mission, summary)

    def _fail_mission(self, mission: Mission, reason: str) -> None:
        mission.status = MissionStatus.failed
        mission.completedAt = utc_now()
        mission.agentStates[ORCHESTRATOR_AGENT_ID] = RuntimeStatus.failed
        self._sync_projection(mission)
        store.save_mission(mission)
        event_bus.emit(
            EventType.mission_failed,
            mission.id,
            f"Mission failed: {reason}",
            ORCHESTRATOR_AGENT_ID,
            metadata={"reason": reason},
        )
        logger.error("mission.failed", missionId=mission.id, reason=reason)

    # ── approvals ───────────────────────────────────────────────────────────

    def decide_approval(
        self, approval_id: str, request: ApprovalDecisionRequest
    ) -> Mission:
        """Record the operator decision and resume in the background.

        Returns immediately so the UI updates without waiting for the rest of
        the mission.
        """
        approval = store.get_approval(approval_id)
        mission = store.get_mission(approval.missionId)

        if approval.status != ApprovalStatus.pending:
            logger.warning(
                "mission.approval_already_decided",
                approvalId=approval_id,
                status=approval.status.value,
            )
            return mission

        granted = request.decision == "granted"
        approval.status = ApprovalStatus.granted if granted else ApprovalStatus.denied
        approval.decision = approval.status
        approval.decidedAt = utc_now()
        approval.decidedBy = request.decidedBy
        store.save_approval(approval)

        task = self._task_for_approval(mission, approval)

        if not granted:
            event_bus.emit(
                EventType.approval_denied,
                mission.id,
                f"Operator denied {approval.tool}",
                approval.agentId,
                metadata={"approvalId": approval.id, "taskId": approval.taskId},
            )
            if task is not None:
                task.status = TaskStatus.failed
                task.error = f"operator denied {approval.tool}"
                task.awaitingApprovalId = None
            mission.awaitingApprovalId = None
            mission.agentStates[approval.agentId] = RuntimeStatus.blocked
            self._skip_unreachable(mission)
            self._fail_mission(mission, f"operator denied {approval.tool}")
            return store.get_mission(mission.id)

        event_bus.emit(
            EventType.approval_granted,
            mission.id,
            f"Operator approved {approval.tool}",
            approval.agentId,
            metadata={"approvalId": approval.id, "taskId": approval.taskId},
        )
        event_bus.emit(
            EventType.agent_resumed,
            mission.id,
            f"{approval.agentId} resumed after approval",
            approval.agentId,
            metadata={"approvalId": approval.id, "taskId": approval.taskId},
        )
        event_bus.emit(
            EventType.mission_resumed,
            mission.id,
            "Mission resumed by operator decision",
            ORCHESTRATOR_AGENT_ID,
            metadata={"approvalId": approval.id},
        )

        mission.status = MissionStatus.running
        mission.awaitingApprovalId = None
        mission.agentStates[approval.agentId] = RuntimeStatus.working
        if task is not None:
            task.status = TaskStatus.in_progress
            task.awaitingApprovalId = None
        self._sync_projection(mission)
        store.save_mission(mission)

        self._spawn(mission.id, self._resume_after_approval(mission.id, approval.id))
        return store.get_mission(mission.id)

    def _task_for_approval(self, mission: Mission, approval) -> MissionTask | None:  # noqa: ANN001
        if approval.taskId:
            task = mission.task_by_id(approval.taskId)
            if task is not None:
                return task
        for task in mission.tasks:
            if task.awaitingApprovalId == approval.id:
                return task
        return None

    async def _resume_after_approval(self, mission_id: str, approval_id: str) -> None:
        try:
            mission = store.get_mission(mission_id)
            approval = store.get_approval(approval_id)
        except KeyError:
            logger.warning("mission.resume_target_missing", missionId=mission_id)
            return

        task = self._task_for_approval(mission, approval)
        if task is not None:
            outcome = await self._run_task(mission_id, task.id, approved_approval_id=approval_id)
            logger.info(
                "mission.resumed_task",
                missionId=mission_id,
                taskId=task.id,
                status=outcome.status.value,
            )
        else:
            logger.warning(
                "mission.resume_task_not_found", missionId=mission_id, approvalId=approval_id
            )
        await self._execute(mission_id)

    # ── projection ──────────────────────────────────────────────────────────

    def _sync_projection(self, mission: Mission) -> None:
        """Refresh the flat `plan` / `currentStep` view the UI consumes."""
        if not mission.tasks:
            mission.plan = []
            mission.currentStep = 0
            return
        try:
            order = [task_id for layer in topological_layers(mission.tasks) for task_id in layer]
        except PlanValidationError:
            order = [task.id for task in mission.tasks]

        by_id = {task.id: task for task in mission.tasks}
        steps: list[MissionPlanStep] = []
        for index, task_id in enumerate(order, start=1):
            task = by_id.get(task_id)
            if task is None:
                continue
            steps.append(
                MissionPlanStep(
                    step=index,
                    agentId=task.agentId,
                    title=task.title,
                    status=_TASK_TO_STEP_STATUS[task.status],
                    taskId=task.id,
                    dependsOn=list(task.dependsOn),
                )
            )
        mission.plan = steps
        mission.currentStep = len(
            [task for task in mission.tasks if task.status == TaskStatus.completed]
        )


mission_service = MissionService()
