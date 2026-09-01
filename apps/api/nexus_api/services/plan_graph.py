"""Pure task-graph validation and scheduling helpers.

This module is deliberately free of I/O, Gemini, and FastAPI so that it can be
unit-tested in isolation. It is the only place allowed to decide whether a plan
is safe to execute — `planner.py` calls it on model output and the orchestrator
calls it again before the first task runs.
"""

from __future__ import annotations

from typing import Any, Iterable

from nexus_api.schemas.domain import AgentCard, MissionTask, TaskStatus

MAX_TITLE_LENGTH = 200
TERMINAL_STATUSES = {TaskStatus.completed, TaskStatus.failed, TaskStatus.skipped}


class PlanValidationError(ValueError):
    """Raised when a plan (from a model or from a fixture) is not executable.

    `reasons` holds every problem found, so a single log line explains exactly
    why untrusted model output was rejected.
    """

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons) if reasons else "plan validation failed")


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    raise TypeError(f"expected list of strings, got {type(value).__name__}")


def validate_plan(
    raw_tasks: Any,
    roster: dict[str, AgentCard],
    *,
    known_tools: Iterable[str] | None = None,
    max_tasks: int = 12,
    max_attempts: int = 3,
) -> list[MissionTask]:
    """Validate untrusted plan data and return typed tasks.

    Rejects, with an explicit reason, any plan that:
      * is not a non-empty list of objects, or exceeds `max_tasks`;
      * has a missing / duplicate / non-string task id;
      * names an `agentId` that is not in the roster;
      * binds a tool the named agent does not own (`AgentCard.tools`);
      * binds a tool that is not a tool the platform implements;
      * declares a `dependsOn` edge to a task id that does not exist;
      * declares a self-dependency;
      * contains a cycle (checked by Kahn topological sort).
    """
    reasons: list[str] = []

    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise PlanValidationError(["plan must be a non-empty list of tasks"])
    if len(raw_tasks) > max_tasks:
        raise PlanValidationError([f"plan has {len(raw_tasks)} tasks, limit is {max_tasks}"])

    tool_whitelist = set(known_tools) if known_tools is not None else None

    seen_ids: set[str] = set()
    normalised: list[dict[str, Any]] = []

    for index, item in enumerate(raw_tasks):
        if not isinstance(item, dict):
            reasons.append(f"task[{index}] is {type(item).__name__}, expected object")
            continue

        task_id = item.get("id")
        if not isinstance(task_id, str) or not task_id.strip():
            reasons.append(f"task[{index}] has a missing or non-string id")
            continue
        task_id = task_id.strip()
        if task_id in seen_ids:
            reasons.append(f"duplicate task id {task_id!r}")
            continue
        seen_ids.add(task_id)

        agent_id = item.get("agentId")
        if not isinstance(agent_id, str) or agent_id not in roster:
            reasons.append(f"task {task_id!r} references unknown agentId {agent_id!r}")
            continue
        agent = roster[agent_id]

        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            title = f"{agent.role} step"
        title = title.strip()[:MAX_TITLE_LENGTH]

        try:
            depends_on = _as_str_list(item.get("dependsOn"))
            tools = _as_str_list(item.get("tools"))
        except TypeError as exc:
            reasons.append(f"task {task_id!r}: {exc}")
            continue

        if task_id in depends_on:
            reasons.append(f"task {task_id!r} depends on itself")
            continue

        illegal_tools = [tool for tool in tools if tool not in agent.tools]
        if illegal_tools:
            reasons.append(
                f"task {task_id!r} binds tools {illegal_tools} that agent "
                f"{agent_id!r} does not own (owned: {agent.tools})"
            )
            continue

        if tool_whitelist is not None:
            unknown = [tool for tool in tools if tool not in tool_whitelist]
            if unknown:
                reasons.append(f"task {task_id!r} binds tools not implemented by the platform: {unknown}")
                continue

        tool_args_raw = item.get("toolArgs") or {}
        tool_args: dict[str, dict[str, Any]] = {}
        if isinstance(tool_args_raw, dict):
            for tool, args in tool_args_raw.items():
                if tool in tools and isinstance(args, dict):
                    tool_args[str(tool)] = dict(args)

        normalised.append(
            {
                "id": task_id,
                "title": title,
                "agentId": agent_id,
                "dependsOn": depends_on,
                "tools": tools,
                "toolArgs": tool_args,
            }
        )

    if reasons:
        raise PlanValidationError(reasons)

    valid_ids = {item["id"] for item in normalised}
    for item in normalised:
        dangling = [dep for dep in item["dependsOn"] if dep not in valid_ids]
        if dangling:
            reasons.append(f"task {item['id']!r} depends on unknown task ids {dangling}")

    if reasons:
        raise PlanValidationError(reasons)

    tasks = [MissionTask(maxAttempts=max_attempts, **item) for item in normalised]

    # Reject cycles. topological_layers raises PlanValidationError on a cycle.
    topological_layers(tasks)
    return tasks


def topological_layers(tasks: list[MissionTask]) -> list[list[str]]:
    """Kahn's algorithm, returning execution *layers*.

    Every task in a layer has all dependencies satisfied by earlier layers, so a
    layer is exactly the set of tasks that may run concurrently. Raises
    `PlanValidationError` if the graph contains a cycle.
    """
    indegree: dict[str, int] = {}
    dependents: dict[str, list[str]] = {task.id: [] for task in tasks}

    for task in tasks:
        deps = [dep for dep in task.dependsOn if dep in dependents]
        indegree[task.id] = len(deps)
        for dep in deps:
            dependents[dep].append(task.id)

    frontier = sorted([task_id for task_id, degree in indegree.items() if degree == 0])
    layers: list[list[str]] = []
    resolved = 0

    while frontier:
        layers.append(frontier)
        resolved += len(frontier)
        next_frontier: list[str] = []
        for task_id in frontier:
            for child in dependents[task_id]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    next_frontier.append(child)
        frontier = sorted(next_frontier)

    if resolved != len(tasks):
        stuck = sorted(task_id for task_id, degree in indegree.items() if degree > 0)
        raise PlanValidationError([f"plan graph contains a dependency cycle involving {stuck}"])

    return layers


def ready_tasks(tasks: list[MissionTask]) -> list[MissionTask]:
    """Tasks whose dependencies have all completed and that are not yet started."""
    by_id = {task.id: task for task in tasks}
    ready: list[MissionTask] = []
    for task in tasks:
        if task.status not in (TaskStatus.pending, TaskStatus.ready):
            continue
        deps = [by_id[dep] for dep in task.dependsOn if dep in by_id]
        if all(dep.status == TaskStatus.completed for dep in deps):
            ready.append(task)
    return ready


def blocked_by_failure(tasks: list[MissionTask]) -> list[MissionTask]:
    """Pending tasks that can never run because an upstream task failed."""
    by_id = {task.id: task for task in tasks}
    blocked: list[MissionTask] = []
    for task in tasks:
        if task.status not in (TaskStatus.pending, TaskStatus.ready):
            continue
        if _has_failed_ancestor(task, by_id, set()):
            blocked.append(task)
    return blocked


def _has_failed_ancestor(
    task: MissionTask, by_id: dict[str, MissionTask], seen: set[str]
) -> bool:
    for dep_id in task.dependsOn:
        if dep_id in seen or dep_id not in by_id:
            continue
        seen.add(dep_id)
        dep = by_id[dep_id]
        if dep.status in (TaskStatus.failed, TaskStatus.skipped):
            return True
        if _has_failed_ancestor(dep, by_id, seen):
            return True
    return False


def downstream_agents(tasks: list[MissionTask], task_id: str) -> list[str]:
    """Agent ids of the direct dependents of `task_id` — the real hand-off edges."""
    return sorted({task.agentId for task in tasks if task_id in task.dependsOn})


def is_terminal(tasks: list[MissionTask]) -> bool:
    return all(task.status in TERMINAL_STATUSES for task in tasks)
