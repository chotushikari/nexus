"""Google ADK runtime.

This module is the specialist-reasoning step for every mission task. Each agent
is built as a real `google.adk.agents.Agent` whose `instruction` is that agent's
own system-prompt markdown (`AgentCard.systemPromptPath`), and executed through
an ADK runner.

Honesty rules enforced here:
  * there is no blanket `except (ImportError, Exception)` — import failures,
    ADK-side failures and unexpected failures are distinguished, logged, and
    surfaced as `AgentReasoning.degraded` plus a reason;
  * when ADK cannot run, the returned text is explicitly labelled as
    deterministic, never dressed up as model output;
  * `/api/health` reports `adk: false` unless an ADK run actually succeeded in
    this process (see `services/capabilities.py`).
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nexus_api.core.config import settings
from nexus_api.core.logging import get_logger
from nexus_api.schemas.domain import AgentCard
from nexus_api.services.capabilities import capabilities

logger = get_logger("adk")

ADK_RUNTIME = "google-adk"
FALLBACK_RUNTIME = "deterministic-fallback"

_IDENTIFIER = re.compile(r"[^0-9a-zA-Z_]")

# Errors raised by ADK / the transport that we treat as recoverable degradation
# rather than programming errors. Deliberately explicit — no bare Exception.
_ADK_RUNTIME_ERRORS: tuple[type[BaseException], ...] = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
    OSError,
    asyncio.TimeoutError,
)


@dataclass(frozen=True)
class AgentReasoning:
    """Result of one specialist reasoning step."""

    text: str
    runtime: str
    degraded: bool = False
    error: str | None = None
    instructionSource: str | None = None


@dataclass(frozen=True)
class AdkAgentDescriptor:
    """Returned when the ADK SDK is not importable, so callers still get a typed
    object describing what *would* have been constructed."""

    agent_id: str
    name: str
    model: str
    instruction: str
    runtime: str = "fallback-descriptor"


def find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists() and (parent / "agents").exists():
            return parent
    return current.parents[4]


PROJECT_ROOT = find_project_root()


# ── SDK availability ────────────────────────────────────────────────────────


def adk_sdk_status() -> tuple[bool, str]:
    """(installed, human-readable note). Never raises."""
    try:
        from google.adk.agents import Agent  # noqa: F401
    except ImportError as exc:
        return False, f"google-adk not importable: {exc}"
    return True, "google-adk importable"


def adk_enabled() -> bool:
    installed, _ = adk_sdk_status()
    return settings.enable_adk and installed


# ── Instruction loading ─────────────────────────────────────────────────────


def load_instruction(agent: AgentCard) -> tuple[str, str]:
    """Return (instruction_text, source).

    Source is the markdown path when the agent has a real system prompt on disk,
    otherwise `agent-card` for a card-derived instruction.
    """
    if agent.systemPromptPath:
        path = PROJECT_ROOT / agent.systemPromptPath
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            logger.warning(
                "adk.instruction_unreadable",
                agentId=agent.id,
                path=str(path),
                reason=str(exc),
            )
        else:
            if text:
                return text, agent.systemPromptPath

    derived = (
        f"You are {agent.name} ({agent.codename}), {agent.role} in the "
        f"{agent.departmentId} department of a governed autonomous enterprise.\n"
        f"Capabilities you are authorised for: {', '.join(agent.capabilities) or 'none'}.\n"
        f"Tools you own: {', '.join(agent.tools) or 'none'}.\n"
        "You may only reason about work inside those capabilities. Never claim to "
        "have performed an action you did not perform. Answer in at most four "
        "sentences, as a decision summary for an operator."
    )
    return derived, "agent-card"


def _adk_agent_name(agent_id: str) -> str:
    name = _IDENTIFIER.sub("_", agent_id)
    return name if name[:1].isalpha() or name.startswith("_") else f"a_{name}"


# ── Agent construction ──────────────────────────────────────────────────────

_AGENT_CACHE: dict[str, Any] = {}


def build_adk_descriptor(agent_id: str, name: str, model: str, instruction: str) -> object:
    """Create a Google ADK `Agent`, or an `AdkAgentDescriptor` when the SDK is
    absent. Kept as the low-level constructor used by the Google-stack tests."""
    try:
        from google.adk.agents import Agent
    except ImportError as exc:
        logger.info("adk.sdk_missing", agentId=agent_id, reason=str(exc))
        return AdkAgentDescriptor(
            agent_id=agent_id, name=name, model=model, instruction=instruction
        )
    return Agent(name=name, model=model, instruction=instruction)


def build_agent_for_card(agent: AgentCard) -> tuple[Any, str]:
    """Build (and memoise) the ADK agent for a roster card.

    Returns (agent_object, instruction_source).
    """
    instruction, source = load_instruction(agent)
    cached = _AGENT_CACHE.get(agent.id)
    if cached is not None:
        return cached, source
    built = build_adk_descriptor(
        agent_id=agent.id,
        name=_adk_agent_name(agent.id),
        model=settings.gemini_model,
        instruction=instruction,
    )
    _AGENT_CACHE[agent.id] = built
    return built, source


def clear_agent_cache() -> None:
    _AGENT_CACHE.clear()


# ── Execution ───────────────────────────────────────────────────────────────


async def _run_adk(agent_obj: Any, prompt: str, session_id: str) -> str:
    """Execute an ADK agent through the ADK runner and return concatenated text.

    Uses the async runner surface when available. Raises on failure; the caller
    decides how to degrade.
    """
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    app_name = "nexus"
    user_id = "nexus-operator"
    runner = InMemoryRunner(agent=agent_obj, app_name=app_name)

    session_service = getattr(runner, "session_service", None)
    session_ref = session_id
    if session_service is not None and hasattr(session_service, "create_session"):
        created = session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        if asyncio.iscoroutine(created):
            created = await created
        session_ref = getattr(created, "id", session_id)

    message = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])

    chunks: list[str] = []
    if hasattr(runner, "run_async"):
        async for event in runner.run_async(
            user_id=user_id, session_id=session_ref, new_message=message
        ):
            chunks.extend(_event_text(event))
    else:  # pragma: no cover - older ADK releases expose only the sync runner
        def _drain() -> list[str]:
            out: list[str] = []
            for event in runner.run(
                user_id=user_id, session_id=session_ref, new_message=message
            ):
                out.extend(_event_text(event))
            return out

        chunks = await asyncio.to_thread(_drain)

    text = "\n".join(chunk.strip() for chunk in chunks if chunk and chunk.strip())
    if not text:
        raise ValueError("ADK run produced no text output")
    return text


def _event_text(event: Any) -> list[str]:
    """Pull text parts out of an ADK event without assuming a concrete shape."""
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) if content is not None else None
    if parts:
        return [str(getattr(part, "text", "") or "") for part in parts]
    text = getattr(event, "text", None)
    return [str(text)] if text else []


async def run_agent_reasoning(
    agent: AgentCard,
    objective: str,
    task_title: str,
    tool_results: dict[str, Any],
    session_id: str,
) -> AgentReasoning:
    """Run the specialist reasoning step for one mission task.

    Never raises: the orchestrator gets a typed result with `degraded` set when
    ADK could not run, so the mission continues and the degradation is visible.
    """
    agent_obj, instruction_source = build_agent_for_card(agent)
    prompt = _build_prompt(agent, objective, task_title, tool_results)

    if not settings.enable_adk:
        reason = "adk disabled by configuration"
        capabilities.record_failure("adk", reason)
        return _fallback(agent, task_title, tool_results, reason, instruction_source)

    installed, note = adk_sdk_status()
    if not installed:
        capabilities.record_failure("adk", note)
        return _fallback(agent, task_title, tool_results, note, instruction_source)

    try:
        text = await asyncio.wait_for(
            _run_adk(agent_obj, prompt, session_id), timeout=settings.adk_timeout_seconds
        )
    except ImportError as exc:
        reason = f"adk runner import failed: {exc}"
        logger.warning("adk.runner_import_failed", agentId=agent.id, reason=str(exc))
        capabilities.record_failure("adk", reason)
        return _fallback(agent, task_title, tool_results, reason, instruction_source)
    except _ADK_RUNTIME_ERRORS as exc:
        reason = f"{type(exc).__name__}: {exc}"
        logger.warning(
            "adk.run_failed", agentId=agent.id, sessionId=session_id, reason=reason
        )
        capabilities.record_failure("adk", reason)
        return _fallback(agent, task_title, tool_results, reason, instruction_source)

    logger.info(
        "adk.run_succeeded",
        agentId=agent.id,
        sessionId=session_id,
        model=settings.gemini_model,
        chars=len(text),
    )
    capabilities.record_success("adk", f"{agent.id} reasoned via ADK ({settings.gemini_model})")
    return AgentReasoning(
        text=text,
        runtime=ADK_RUNTIME,
        degraded=False,
        instructionSource=instruction_source,
    )


def _build_prompt(
    agent: AgentCard, objective: str, task_title: str, tool_results: dict[str, Any]
) -> str:
    lines = [
        f"Mission objective: {objective}",
        f"Your assigned task: {task_title}",
        "",
        "Verified tool output available to you:",
    ]
    if tool_results:
        for tool, result in tool_results.items():
            lines.append(f"- {tool}: {result}")
    else:
        lines.append("- (none; reason from your role and the objective only)")
    lines += [
        "",
        "Produce a short decision summary for the operator. State your finding, "
        "your confidence, and what the next department needs from you. Do not "
        "invent data that is not in the tool output above.",
    ]
    return "\n".join(lines)


def _fallback(
    agent: AgentCard,
    task_title: str,
    tool_results: dict[str, Any],
    reason: str,
    instruction_source: str | None,
) -> AgentReasoning:
    """Deterministic, explicitly-labelled stand-in for a model reasoning step."""
    facts = "; ".join(f"{tool}={result}" for tool, result in tool_results.items())
    text = (
        f"[deterministic summary — no model reasoning: {reason}] "
        f"{agent.name} ({agent.role}) completed '{task_title}'."
    )
    if facts:
        text += f" Tool evidence: {facts}."
    return AgentReasoning(
        text=text,
        runtime=FALLBACK_RUNTIME,
        degraded=True,
        error=reason,
        instructionSource=instruction_source,
    )


def run_adk_agent(agent_obj: Any, prompt: str, session_id: str = "default-session") -> str:
    """Synchronous convenience wrapper kept for scripts and ad-hoc use.

    Prefer `run_agent_reasoning`. Raises on ADK failure instead of swallowing it.
    """
    return asyncio.run(_run_adk(agent_obj, prompt, session_id))
