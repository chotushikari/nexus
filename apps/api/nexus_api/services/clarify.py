"""Objective clarification — NEXUS asks better questions before planning.

Like a good chief of staff, the planner refuses to guess. Given a raw
objective it returns a handful of sharp, high-leverage questions with
suggested answers, so the mission graph is built on understanding instead
of assumptions.

Gemini-backed when available; a deterministic heuristic set keeps the loop
working offline (reported honestly via `source`).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pydantic import BaseModel, Field

from nexus_api.core.config import settings
from nexus_api.core.logging import get_logger
from nexus_api.services.capabilities import capabilities

logger = get_logger("clarify")

_CLARIFY_TIMEOUT_SECONDS = 14.0


class ClarifyQuestion(BaseModel):
    id: str
    question: str
    why: str = ""
    suggestions: list[str] = Field(default_factory=list)


class ClarifyResult(BaseModel):
    questions: list[ClarifyQuestion]
    source: str  # "gemini" | "heuristic"


# ── Deterministic fallback ───────────────────────────────────────────────────

_HEURISTIC_QUESTIONS = [
    ClarifyQuestion(
        id="outcome",
        question="What does 'done' look like — what artifact should be on your desk when this finishes?",
        why="The workforce optimises for a deliverable, not a vibe.",
        suggestions=[
            "A one-page decision memo I can act on",
            "A working prototype or landing page",
            "A scored shortlist with a recommendation",
        ],
    ),
    ClarifyQuestion(
        id="constraints",
        question="What hard constraints should the plan respect (budget, deadline, tools you already use)?",
        why="Constraints shape which agents and tools get scheduled.",
        suggestions=[
            "Bootstrapped — free tools only",
            "This week, part-time hours",
            "No constraints, optimise for quality",
        ],
    ),
    ClarifyQuestion(
        id="audience",
        question="Who is this for — who buys, reads, or approves the result?",
        why="Research and marketing depth depends on the audience.",
        suggestions=[
            "Consumers (B2C)",
            "Small businesses (B2B SMB)",
            "Enterprise buyers",
        ],
    ),
    ClarifyQuestion(
        id="risk",
        question="How aggressive should the workforce be — read-only research, or actions with real-world effects?",
        why="Sensitive actions route through the approval gate; you choose the tripwire.",
        suggestions=[
            "Read-only for now",
            "Draft everything, send nothing",
            "Go ahead and publish/shipped-scale actions",
        ],
    ),
]


def _heuristic_clarify(objective: str) -> ClarifyResult:
    text = (objective or "").lower()
    questions = list(_HEURISTIC_QUESTIONS)
    if any(k in text for k in ("scrape", "competitor", "market", "research", "pricing")):
        questions.insert(
            1,
            ClarifyQuestion(
                id="scope",
                question="Which competitors or market segments matter most — and how deep should we dig?",
                why="Scraping and research breadth is the biggest cost/time lever.",
                suggestions=[
                    "Top 3 direct competitors, deep",
                    "Broad market scan, shallow",
                    "You pick — surprise me with the landscape",
                ],
            ),
        )
    if any(k in text for k in ("launch", "market", "marketing", "gtm", "landing", "product")):
        questions.insert(
            2,
            ClarifyQuestion(
                id="channel",
                question="Where should the first marketing push land?",
                why="The GTM plan is only as good as its first channel bet.",
                suggestions=[
                    "Content + SEO",
                    "Cold outreach (email/LinkedIn)",
                    "Product Hunt / launch communities",
                ],
            ),
        )
    return ClarifyResult(questions=questions[:5], source="heuristic")


# ── Gemini path ──────────────────────────────────────────────────────────────

_SYSTEM = (
    "You are NEXUS chief-of-staff. Given a founder's raw objective, ask the 3-5 "
    "highest-leverage clarifying questions that would most change how an autonomous "
    "workforce should plan and execute it. Be specific to the objective, never "
    "generic. Each question: id (snake_case), question (one sentence, sharp), why "
    "(one short sentence), suggestions (2-3 crisp one-line answers the founder can "
    "tap). Reply ONLY with JSON: {\"questions\":[...]}."
)


async def clarify_objective(objective: str) -> ClarifyResult:
    from nexus_api.services.planner import _build_client  # reuse the auth logic

    try:
        client = _build_client()
    except Exception as exc:  # noqa: BLE001 - degrade honestly
        logger.warning("clarify.gemini_unavailable", reason=str(exc))
        capabilities.record_failure("gemini", f"clarify unavailable: {exc}")
        return _heuristic_clarify(objective)

    payload = {
        "system_instruction": _SYSTEM,
        "contents": [{"role": "user", "parts": [{"text": objective}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.4,
            "maxOutputTokens": 4096,
        },
    }

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                lambda: client.models.generate_content(
                    model=settings.gemini_model_lite,
                    contents=payload["contents"],
                    config={
                        "system_instruction": payload["system_instruction"],
                        "response_mime_type": "application/json",
                        "temperature": 0.4,
                        "max_output_tokens": 4096,
                    },
                ),
            ),
            timeout=_CLARIFY_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        capabilities.record_failure("gemini", f"clarify timeout after {_CLARIFY_TIMEOUT_SECONDS}s")
        return _heuristic_clarify(objective)
    except Exception as exc:  # noqa: BLE001 - never let clarify kill the request
        logger.warning("clarify.gemini_failed", reason=f"{type(exc).__name__}: {exc}")
        capabilities.record_failure("gemini", f"clarify failed: {exc}")
        return _heuristic_clarify(objective)

    try:
        data: dict[str, Any] = json.loads(response.text or "{}")
        questions = [
            ClarifyQuestion(
                id=str(q.get("id") or f"q{i}"),
                question=str(q.get("question") or "").strip(),
                why=str(q.get("why") or "").strip(),
                suggestions=[str(s) for s in (q.get("suggestions") or [])][:4],
            )
            for i, q in enumerate(data.get("questions", []))
            if str(q.get("question") or "").strip()
        ][:5]
    except (ValueError, TypeError, AttributeError) as exc:
        logger.warning("clarify.parse_failed", reason=str(exc))
        capabilities.record_failure("gemini", f"clarify parse: {exc}")
        return _heuristic_clarify(objective)

    if not questions:
        capabilities.record_failure("gemini", "clarify returned no questions")
        return _heuristic_clarify(objective)

    capabilities.record_success("gemini", "clarify answered with Gemini")
    return ClarifyResult(questions=questions, source="gemini")
