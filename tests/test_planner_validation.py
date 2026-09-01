"""Plan validation: untrusted model output must never reach the executor.

SANDBOX NOTE: authored where pytest/pydantic were unavailable, so this file was
NOT executed at authoring time. It requires `pydantic` (see tests/conftest.py).

What this file proves:
  * every adversarial plan shape is rejected by `plan_graph.validate_plan` with
    an explicit reason (no silent coercion);
  * `PlanSource.gemini` is set only after `validate_plan` succeeded — a rejected
    model response degrades to `deterministic_fallback` with `model is None`;
  * the capability registry is not marked `gemini exercised` for rejected output;
  * no test here performs network I/O: the Gemini transport is replaced.
"""

from __future__ import annotations

import json

import pytest

from conftest import requires_backend

requires_backend()

from nexus_api.core.config import settings  # noqa: E402
from nexus_api.schemas.domain import PlanSource  # noqa: E402
from nexus_api.services import planner as planner_module  # noqa: E402
from nexus_api.services.capabilities import capabilities  # noqa: E402
from nexus_api.services.plan_graph import (  # noqa: E402
    PlanValidationError,
    topological_layers,
    validate_plan,
)
from nexus_api.services.planner import (  # noqa: E402
    IMPLEMENTED_TOOLS,
    mission_planner,
    parse_plan_payload,
)


def _validate(raw, roster):
    return validate_plan(
        raw,
        roster,
        known_tools=IMPLEMENTED_TOOLS,
        max_tasks=settings.planner_max_tasks,
        max_attempts=settings.agent_max_attempts,
    )


def _task(task_id, agent_id, tools=None, depends=None, title="step"):
    return {
        "id": task_id,
        "title": title,
        "agentId": agent_id,
        "dependsOn": list(depends or []),
        "tools": list(tools or []),
    }


# ── the happy path, so the rejections below mean something ──────────────────


def test_a_well_formed_plan_is_accepted_and_layered(roster):
    tasks = _validate(
        [
            _task("t1", "elena-rao", ["company_search"]),
            _task("t2", "marcus-chen", ["sanctions_check"], ["t1"]),
            _task("t3", "david-brooks", ["financial_lookup"], ["t1"]),
            _task("t4", "sarah-patel", ["supplier_score"], ["t2", "t3"]),
        ],
        roster,
    )

    assert [task.id for task in tasks] == ["t1", "t2", "t3", "t4"]
    # A diamond: t2 and t3 share a layer, so they are genuinely parallelisable.
    assert topological_layers(tasks) == [["t1"], ["t2", "t3"], ["t4"]]
    assert all(task.maxAttempts == settings.agent_max_attempts for task in tasks)


# ── adversarial shapes ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param([], id="empty-list"),
        pytest.param({}, id="empty-dict"),
        pytest.param({"tasks": []}, id="dict-not-list"),
        pytest.param(None, id="none"),
        pytest.param("task-research", id="bare-string"),
        pytest.param(42, id="int"),
        pytest.param([1, 2, 3], id="list-of-scalars"),
        pytest.param(["not-an-object"], id="list-of-strings"),
    ],
)
def test_non_list_or_empty_payloads_are_rejected(payload, roster):
    with pytest.raises(PlanValidationError) as excinfo:
        _validate(payload, roster)
    assert excinfo.value.reasons, "a rejection must always carry at least one reason"


def test_unknown_agent_id_is_rejected(roster):
    with pytest.raises(PlanValidationError) as excinfo:
        _validate([_task("t1", "totally-not-an-agent", ["company_search"])], roster)

    assert any("unknown agentId" in reason for reason in excinfo.value.reasons)


def test_tool_not_owned_by_the_named_agent_is_rejected(roster):
    """The classic privilege-escalation attempt: give the research agent the
    finance agent's payment tool."""
    with pytest.raises(PlanValidationError) as excinfo:
        _validate([_task("t1", "elena-rao", ["create_payment"])], roster)

    reasons = " ".join(excinfo.value.reasons)
    assert "create_payment" in reasons
    assert "does not own" in reasons


def test_tool_the_platform_does_not_implement_is_rejected(roster):
    """`victor-stone` really does own `security_scan` in the roster, but the
    runtime has no dispatch branch for it, so a plan binding it is not
    executable and must be refused rather than fail mid-mission."""
    assert "security_scan" in roster["victor-stone"].tools
    assert "security_scan" not in IMPLEMENTED_TOOLS

    with pytest.raises(PlanValidationError) as excinfo:
        _validate([_task("t1", "victor-stone", ["security_scan"])], roster)

    assert any("not implemented" in reason for reason in excinfo.value.reasons)


def test_dangling_depends_on_is_rejected(roster):
    with pytest.raises(PlanValidationError) as excinfo:
        _validate(
            [
                _task("t1", "elena-rao", ["company_search"]),
                _task("t2", "marcus-chen", ["sanctions_check"], ["t-does-not-exist"]),
            ],
            roster,
        )

    assert any("unknown task ids" in reason for reason in excinfo.value.reasons)


def test_self_dependency_is_rejected(roster):
    with pytest.raises(PlanValidationError) as excinfo:
        _validate([_task("t1", "elena-rao", ["company_search"], ["t1"])], roster)

    assert any("depends on itself" in reason for reason in excinfo.value.reasons)


def test_two_cycle_is_rejected(roster):
    with pytest.raises(PlanValidationError) as excinfo:
        _validate(
            [
                _task("t1", "elena-rao", ["company_search"], ["t2"]),
                _task("t2", "marcus-chen", ["sanctions_check"], ["t1"]),
            ],
            roster,
        )

    reasons = " ".join(excinfo.value.reasons)
    assert "cycle" in reasons
    assert "t1" in reasons and "t2" in reasons


def test_three_cycle_is_rejected(roster):
    """A 3-cycle has no self-edge and no dangling id, so only the topological
    sort can catch it. This is the case a naive validator misses."""
    with pytest.raises(PlanValidationError) as excinfo:
        _validate(
            [
                _task("t1", "elena-rao", ["company_search"], ["t3"]),
                _task("t2", "marcus-chen", ["sanctions_check"], ["t1"]),
                _task("t3", "david-brooks", ["financial_lookup"], ["t2"]),
            ],
            roster,
        )

    reasons = " ".join(excinfo.value.reasons)
    assert "cycle" in reasons
    assert {"t1", "t2", "t3"}.issubset(set(reasons.replace("'", " ").split()))


def test_cycle_buried_under_a_valid_prefix_is_rejected(roster):
    """Two clean tasks followed by a cycle: partial validity must not buy a pass."""
    with pytest.raises(PlanValidationError):
        _validate(
            [
                _task("t1", "elena-rao", ["company_search"]),
                _task("t2", "marcus-chen", ["sanctions_check"], ["t1"]),
                _task("t3", "david-brooks", ["financial_lookup"], ["t4"]),
                _task("t4", "sarah-patel", ["supplier_score"], ["t3"]),
            ],
            roster,
        )


def test_duplicate_task_ids_are_rejected(roster):
    with pytest.raises(PlanValidationError) as excinfo:
        _validate(
            [
                _task("t1", "elena-rao", ["company_search"]),
                _task("t1", "marcus-chen", ["sanctions_check"]),
            ],
            roster,
        )

    assert any("duplicate task id" in reason for reason in excinfo.value.reasons)


@pytest.mark.parametrize(
    "task_id", [pytest.param("", id="empty"), pytest.param("   ", id="whitespace")]
)
def test_blank_task_id_is_rejected(task_id, roster):
    with pytest.raises(PlanValidationError) as excinfo:
        _validate([_task(task_id, "elena-rao", ["company_search"])], roster)

    assert any("missing or non-string id" in reason for reason in excinfo.value.reasons)


def test_non_string_task_id_is_rejected(roster):
    with pytest.raises(PlanValidationError):
        _validate([_task(7, "elena-rao", ["company_search"])], roster)


def test_over_size_plan_is_rejected(roster):
    oversized = [_task(f"t{index}", "elena-rao", ["company_search"]) for index in range(50)]

    with pytest.raises(PlanValidationError) as excinfo:
        _validate(oversized, roster)

    assert any("limit is" in reason for reason in excinfo.value.reasons)


def test_tool_args_for_unbound_tools_are_dropped(roster):
    """Model-supplied `toolArgs` for a tool the task does not own must not
    survive validation — otherwise arbitrary payloads ride along."""
    tasks = _validate(
        [
            {
                **_task("t1", "david-brooks", ["financial_lookup"]),
                "toolArgs": {
                    "financial_lookup": {"vendorId": "kestrel-components"},
                    "create_payment": {"amount": 999999999, "recipient": "attacker"},
                },
            }
        ],
        roster,
    )

    assert set(tasks[0].toolArgs) == {"financial_lookup"}
    assert "create_payment" not in tasks[0].toolArgs


def test_over_long_title_is_truncated_not_rejected(roster):
    tasks = _validate(
        [_task("t1", "elena-rao", ["company_search"], title="x" * 5000)], roster
    )
    assert len(tasks[0].title) <= 200


def test_every_rejection_reason_is_reported_not_just_the_first(roster):
    """A single log line must explain everything wrong with model output."""
    with pytest.raises(PlanValidationError) as excinfo:
        _validate(
            [
                _task("t1", "nobody-at-all", ["company_search"]),
                _task("t2", "elena-rao", ["create_payment"]),
            ],
            roster,
        )

    assert len(excinfo.value.reasons) >= 2


# ── response parsing ────────────────────────────────────────────────────────


def test_parse_plan_payload_tolerates_code_fences():
    payload = parse_plan_payload('```json\n{"tasks": [{"id": "t1"}]}\n```')
    assert payload == [{"id": "t1"}]


def test_parse_plan_payload_accepts_a_bare_array():
    assert parse_plan_payload('[{"id": "t1"}]') == [{"id": "t1"}]


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("this is not json at all", id="prose"),
        pytest.param('{"tasks": {"id": "t1"}}', id="tasks-not-a-list"),
        pytest.param('{"plan": []}', id="wrong-key"),
        pytest.param("", id="empty"),
        pytest.param('{"tasks": [{"id": "t1"},]}', id="trailing-comma"),
    ],
)
def test_parse_plan_payload_rejects_malformed_responses(text):
    with pytest.raises(PlanValidationError):
        parse_plan_payload(text)


# ── PlanSource honesty: gemini only after validation ────────────────────────


class _FakeClient:
    """Stands in for `google.genai.Client`. Deliberately has no `aio` attribute
    so `planner._generate` would take the thread path — but `_generate` itself is
    patched in these tests, so nothing is ever dispatched anywhere."""

    aio = None


def _patch_gemini(monkeypatch, responses):
    """Make the planner believe Gemini is reachable and hand it canned text.

    `responses` is a list consumed one entry per attempt; an entry may be a
    string (returned) or an Exception instance (raised).
    """
    calls = {"count": 0}
    queue = list(responses)
    exhausted = "the fake transport ran out of canned responses"

    monkeypatch.setattr(planner_module, "_build_client", lambda: _FakeClient())

    async def fake_generate(client, prompt):
        calls["count"] += 1
        assert "roster" in prompt, "the planner must send the real roster to the model"
        item = queue.pop(0) if queue else RuntimeError(exhausted)
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr(planner_module, "_generate", fake_generate)
    return calls


def _valid_model_response():
    return json.dumps(
        {
            "tasks": [
                {
                    "id": "t1",
                    "title": "Verify the vendor",
                    "agentId": "elena-rao",
                    "dependsOn": [],
                    "tools": ["company_search", "company_profile"],
                },
                {
                    "id": "t2",
                    "title": "Clear sanctions",
                    "agentId": "marcus-chen",
                    "dependsOn": ["t1"],
                    "tools": ["sanctions_check"],
                },
                {
                    "id": "t3",
                    "title": "Assess financial risk",
                    "agentId": "david-brooks",
                    "dependsOn": ["t1"],
                    "tools": ["financial_lookup", "risk_calculator"],
                },
            ]
        }
    )


async def test_valid_model_output_is_labelled_gemini(monkeypatch, roster):
    calls = _patch_gemini(monkeypatch, [_valid_model_response()])

    result = await mission_planner.plan(
        "mission-test", "verify and clear the vendor", "kestrel-components", roster
    )

    assert calls["count"] == 1
    assert result.source == PlanSource.gemini
    assert result.is_gemini is True
    assert result.model == settings.gemini_model
    assert [task.id for task in result.tasks] == ["t1", "t2", "t3"]
    assert result.layers == [["t1"], ["t2", "t3"]]
    # Only now may the health endpoint claim gemini.
    assert capabilities.exercised("gemini") is True


@pytest.mark.parametrize(
    "bad_response",
    [
        pytest.param("absolutely not json", id="not-json"),
        pytest.param('{"tasks": []}', id="empty-task-list"),
        pytest.param('{"plan": [{"id": "t1"}]}', id="wrong-top-level-key"),
        pytest.param(
            json.dumps(
                {"tasks": [{"id": "t1", "agentId": "ghost-agent", "dependsOn": [], "tools": []}]}
            ),
            id="unknown-agent",
        ),
        pytest.param(
            json.dumps(
                {
                    "tasks": [
                        {
                            "id": "t1",
                            "agentId": "elena-rao",
                            "dependsOn": [],
                            "tools": ["create_payment"],
                        }
                    ]
                }
            ),
            id="tool-not-owned",
        ),
        pytest.param(
            json.dumps(
                {
                    "tasks": [
                        {
                            "id": "t1",
                            "agentId": "elena-rao",
                            "dependsOn": ["t9"],
                            "tools": ["company_search"],
                        }
                    ]
                }
            ),
            id="dangling-dependency",
        ),
        pytest.param(
            json.dumps(
                {
                    "tasks": [
                        {
                            "id": "t1",
                            "agentId": "elena-rao",
                            "dependsOn": ["t1"],
                            "tools": ["company_search"],
                        }
                    ]
                }
            ),
            id="self-dependency",
        ),
        pytest.param(
            json.dumps(
                {
                    "tasks": [
                        {
                            "id": "t1",
                            "agentId": "elena-rao",
                            "dependsOn": ["t2"],
                            "tools": ["company_search"],
                        },
                        {
                            "id": "t2",
                            "agentId": "marcus-chen",
                            "dependsOn": ["t1"],
                            "tools": ["sanctions_check"],
                        },
                    ]
                }
            ),
            id="two-cycle",
        ),
        pytest.param(
            json.dumps(
                {
                    "tasks": [
                        {
                            "id": "t1",
                            "agentId": "elena-rao",
                            "dependsOn": ["t3"],
                            "tools": ["company_search"],
                        },
                        {
                            "id": "t2",
                            "agentId": "marcus-chen",
                            "dependsOn": ["t1"],
                            "tools": ["sanctions_check"],
                        },
                        {
                            "id": "t3",
                            "agentId": "david-brooks",
                            "dependsOn": ["t2"],
                            "tools": ["financial_lookup"],
                        },
                    ]
                }
            ),
            id="three-cycle",
        ),
        pytest.param(
            json.dumps(
                {
                    "tasks": [
                        {
                            "id": "dup",
                            "agentId": "elena-rao",
                            "dependsOn": [],
                            "tools": ["company_search"],
                        },
                        {
                            "id": "dup",
                            "agentId": "marcus-chen",
                            "dependsOn": [],
                            "tools": ["sanctions_check"],
                        },
                    ]
                }
            ),
            id="duplicate-ids",
        ),
    ],
)
async def test_rejected_model_output_never_claims_gemini(bad_response, monkeypatch, roster):
    """The central honesty invariant.

    Whatever the model says, if `validate_plan` refuses it the mission plan must
    be reported as `deterministic_fallback` with `planModel is None`, and the
    capability registry must not mark gemini as exercised.
    """
    attempts = max(1, settings.planner_max_attempts)
    calls = _patch_gemini(monkeypatch, [bad_response] * attempts)

    result = await mission_planner.plan(
        "mission-test",
        "verify the vendor, clear compliance, assess financial risk, onboard",
        "kestrel-components",
        roster,
    )

    assert calls["count"] == attempts, "the planner must exhaust its retry budget, then degrade"
    assert result.source == PlanSource.deterministic_fallback
    assert result.is_gemini is False
    assert result.model is None
    assert "Gemini was not used" in result.notes
    assert capabilities.exercised("gemini") is False
    # The fallback graph is still a real, executable, validated graph.
    assert result.tasks
    assert result.layers


async def test_planner_retries_once_then_accepts(monkeypatch, roster):
    """A single bad response must not poison the mission: attempt 2 can succeed,
    and only then is `gemini` claimed."""
    calls = _patch_gemini(monkeypatch, ["garbage", _valid_model_response()])

    result = await mission_planner.plan(
        "mission-test", "verify the vendor", "kestrel-components", roster
    )

    assert calls["count"] == 2
    assert result.source == PlanSource.gemini
    assert capabilities.exercised("gemini") is True


async def test_transport_errors_degrade_instead_of_crashing(monkeypatch, roster):
    calls = _patch_gemini(
        monkeypatch, [RuntimeError("connection reset")] * max(1, settings.planner_max_attempts)
    )

    result = await mission_planner.plan(
        "mission-test", "verify the vendor", "kestrel-components", roster
    )

    assert calls["count"] == max(1, settings.planner_max_attempts)
    assert result.source == PlanSource.deterministic_fallback
    assert result.model is None
    assert capabilities.exercised("gemini") is False


async def test_no_credentials_means_no_call_is_attempted_at_all(roster):
    """With credentials forced absent by the `reset_runtime` fixture, the planner
    must not even construct a client — this is what keeps the suite offline."""
    result = await mission_planner.plan(
        "mission-test",
        "verify the vendor, clear compliance, assess financial risk, onboard",
        "kestrel-components",
        roster,
    )

    assert result.source == PlanSource.deterministic_fallback
    assert result.model is None
    assert capabilities.exercised("gemini") is False


# ── deterministic fallback quality ──────────────────────────────────────────


async def test_fallback_graph_is_diamond_shaped_not_a_chain(roster):
    """The fallback must expose genuine parallelism, otherwise the "concurrent
    execution" claim is untestable and untrue."""
    result = await mission_planner.plan(
        "mission-test",
        "verify the vendor, clear sanctions and compliance, assess financial "
        "risk and payment terms, prepare procurement onboarding",
        "kestrel-components",
        roster,
    )

    assert result.layers == [
        ["task-research"],
        ["task-compliance", "task-finance"],
        ["task-procurement"],
    ]
    widest = max(len(layer) for layer in result.layers)
    assert widest >= 2, "no layer has two tasks, so nothing can run concurrently"


async def test_fallback_selects_stages_from_the_objective(roster):
    # Deliberately avoids the words "vendor"/"supplier"/"terms", each of which is
    # a procurement keyword — the point is that an unrelated stage is *not* added.
    result = await mission_planner.plan(
        "mission-test", "just run a sanctions screen on this counterparty", "kestrel-components", roster
    )

    ids = {task.id for task in result.tasks}
    assert "task-compliance" in ids
    # Compliance needs the company profile, so research is always pulled in first.
    assert "task-research" in ids
    assert "task-finance" not in ids
    assert "task-procurement" not in ids


async def test_fallback_payment_amount_is_above_the_approval_threshold(roster):
    """The governance demo depends on `create_payment` tripping REQUIRE_APPROVAL.
    If the seeded amount ever drops below the finance threshold the whole
    human-in-the-loop story silently stops being exercised."""
    from nexus_api.services.policy import POLICY_RULES

    threshold = next(
        rule["threshold"]
        for rule in POLICY_RULES["david-brooks"]["approvalRequired"]
        if isinstance(rule, dict) and rule.get("tool") == "create_payment"
    )

    result = await mission_planner.plan(
        "mission-test",
        "assess financial risk and configure payment terms",
        "kestrel-components",
        roster,
    )
    finance = next(task for task in result.tasks if task.id == "task-finance")

    assert finance.toolArgs["create_payment"]["amount"] > threshold


async def test_plan_created_event_reports_the_source_honestly(roster):
    from nexus_api.schemas.domain import EventType
    from nexus_api.services.storage import store

    result = await mission_planner.plan(
        "mission-honesty", "verify the vendor", "kestrel-components", roster
    )

    events = [
        event
        for event in store.list_events("mission-honesty")
        if event.type == EventType.plan_created
    ]
    assert len(events) == 1
    assert events[0].metadata["planSource"] == result.source.value
    assert events[0].metadata["planModel"] == result.model
    assert events[0].metadata["layers"] == result.layers


def test_roster_context_hides_agents_with_no_executable_tool(roster):
    """A tier-3 registry agent owns no implemented tool, so offering it to the
    planner can only produce an unexecutable plan."""
    context = planner_module.roster_context(roster)
    offered = {entry["agentId"] for entry in context}

    assert "elena-rao" in offered
    assert "iris-vance" not in offered, "an agent with no runnable tool must not be offered"
    for entry in context:
        assert entry["tools"], "an offered agent must have at least one executable tool"
        assert set(entry["tools"]).issubset(IMPLEMENTED_TOOLS)
