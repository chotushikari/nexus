"""Persistence: state must survive a process restart with no credentials at all.

SANDBOX NOTE: authored where pytest/pydantic were unavailable, so this file was
NOT executed at authoring time. It requires `pydantic` (see tests/conftest.py).
`tests/manual_verify.py` covers the on-disk *layout* of `json_store` with the
stdlib only, which is the part that could be checked without pydantic.

What this file proves:
  * `JsonFileStore` round-trips missions, approvals and events with full fidelity
    (statuses, task graph, parked-branch pointers, timestamps);
  * re-instantiating the store over the same directory recovers everything —
    this is the API-restart simulation;
  * `DualStore` reads *through* to the durable backend on a cache miss, so a
    mission created before a restart is readable afterwards;
  * a mission parked on a human approval is recoverable in its parked state,
    which is the case that actually matters for the demo;
  * corrupt / partial state degrades to a warning and a skipped record instead of
    taking the process down.
"""

from __future__ import annotations

import json

import pytest

from conftest import requires_backend

requires_backend()

from nexus_api.core.config import StoreBackend, settings  # noqa: E402
from nexus_api.schemas.domain import (  # noqa: E402
    Approval,
    ApprovalStatus,
    Event,
    EventType,
    Mission,
    MissionStatus,
    MissionTask,
    PlanSource,
    StartMissionRequest,
    TaskStatus,
    new_id,
)
from nexus_api.services.json_store import JsonFileStore  # noqa: E402
from nexus_api.services.mission import mission_service  # noqa: E402
from nexus_api.services.storage import DualStore, store  # noqa: E402


def _mission(**overrides) -> Mission:
    fields = {
        "id": new_id("mission"),
        "enterpriseId": settings.enterprise_id,
        "title": "Kestrel Components Vendor Onboarding",
        "objective": "Evaluate the vendor and onboard if compliant.",
        "vendorId": settings.default_vendor_id,
        "status": MissionStatus.awaiting_approval,
        "planSource": PlanSource.deterministic_fallback,
        "planNotes": "fallback planner",
        "tasks": [
            MissionTask(
                id="task-research",
                title="Verify the vendor",
                agentId="elena-rao",
                tools=["company_search"],
                status=TaskStatus.completed,
                attempts=1,
                result={"company_search": {"id": "kestrel-components"}},
                reasoning="verified",
                reasoningRuntime="deterministic-fallback",
            ),
            MissionTask(
                id="task-finance",
                title="Configure payment terms",
                agentId="david-brooks",
                dependsOn=["task-research"],
                tools=["financial_lookup", "create_payment"],
                toolArgs={"create_payment": {"amount": 500000, "currency": "INR"}},
                status=TaskStatus.blocked,
                attempts=1,
                pendingTool="create_payment",
                result={"financial_lookup": {"annualRevenueUsd": 28750000}},
            ),
        ],
        "results": {"task-research": {"agentId": "elena-rao"}},
        "degraded": {"planner": "no credentials"},
    }
    fields.update(overrides)
    return Mission(**fields)


def _approval(mission_id: str, **overrides) -> Approval:
    fields = {
        "missionId": mission_id,
        "agentId": "david-brooks",
        "tool": "create_payment",
        "request": {"amount": 500000, "currency": "INR"},
        "reason": "Payments above threshold require human approval",
        "policyId": "finance-strict",
        "taskId": "task-finance",
    }
    fields.update(overrides)
    return Approval(**fields)


# ── JsonFileStore round-trip ────────────────────────────────────────────────


def test_mission_round_trips_through_the_json_store(tmp_path):
    backend = JsonFileStore(tmp_path / "state")
    mission = _mission()

    backend.save_mission(mission)
    loaded = backend.get_mission(mission.id)

    assert loaded is not None
    assert loaded.id == mission.id
    assert loaded.status == MissionStatus.awaiting_approval
    assert loaded.enterpriseId == settings.enterprise_id
    assert loaded.planSource == PlanSource.deterministic_fallback
    assert loaded.degraded == {"planner": "no credentials"}
    assert [task.id for task in loaded.tasks] == ["task-research", "task-finance"]

    finance = loaded.task_by_id("task-finance")
    assert finance.status == TaskStatus.blocked
    assert finance.pendingTool == "create_payment"
    assert finance.dependsOn == ["task-research"]
    assert finance.toolArgs["create_payment"]["amount"] == 500000
    assert finance.result == {"financial_lookup": {"annualRevenueUsd": 28750000}}
    assert loaded.task_by_id("task-research").result["company_search"]["id"] == (
        "kestrel-components"
    )


def test_approval_round_trips_through_the_json_store(tmp_path):
    backend = JsonFileStore(tmp_path / "state")
    approval = _approval("mission-x", status=ApprovalStatus.granted, decidedBy="operator")

    backend.save_approval(approval)
    loaded = backend.get_approval(approval.id)

    assert loaded is not None
    assert loaded.status == ApprovalStatus.granted
    assert loaded.decidedBy == "operator"
    assert loaded.taskId == "task-finance"
    assert loaded.request["amount"] == 500000


def test_events_round_trip_as_an_append_only_log(tmp_path):
    backend = JsonFileStore(tmp_path / "state")
    events = [
        Event(
            type=EventType.mission_created,
            missionId="mission-log",
            summary="created",
            agentId="alex-morgan",
        ),
        Event(
            type=EventType.policy_blocked,
            missionId="mission-log",
            summary="blocked",
            agentId="elena-rao",
            metadata={"reason": "identity_scope_violation"},
        ),
        Event(
            type=EventType.mission_created,
            missionId="mission-other",
            summary="other mission",
        ),
    ]
    for event in events:
        backend.save_event(event)

    for_log = backend.list_events("mission-log")
    assert [event.type for event in for_log] == [
        EventType.mission_created,
        EventType.policy_blocked,
    ]
    assert for_log[1].metadata["reason"] == "identity_scope_violation"
    assert len(backend.list_events()) == 3
    assert backend.list_events("mission-nonexistent") == []

    # One file per mission, JSON-lines, so the log is greppable and appendable.
    log = (tmp_path / "state" / "events" / "mission-log.jsonl").read_text(encoding="utf-8")
    lines = [line for line in log.splitlines() if line.strip()]
    assert len(lines) == 2
    assert json.loads(lines[0])["type"] == "MISSION_CREATED"


def test_reinstantiating_the_store_recovers_everything(tmp_path):
    """The API-restart simulation at the durable-store layer."""
    state = tmp_path / "state"
    mission = _mission()
    approval = _approval(mission.id)

    first = JsonFileStore(state)
    first.save_mission(mission)
    first.save_approval(approval)
    first.save_event(
        Event(type=EventType.approval_requested, missionId=mission.id, summary="needs approval")
    )

    del first
    second = JsonFileStore(state)

    recovered = second.get_mission(mission.id)
    assert recovered is not None
    assert recovered.id == mission.id
    assert recovered.status == MissionStatus.awaiting_approval
    assert recovered.task_by_id("task-finance").pendingTool == "create_payment"
    assert [item.id for item in second.list_missions()] == [mission.id]
    assert second.get_approval(approval.id).status == ApprovalStatus.pending
    assert [item.id for item in second.list_approvals(ApprovalStatus.pending)] == [approval.id]
    assert [event.type for event in second.list_events(mission.id)] == [
        EventType.approval_requested
    ]


def test_missing_documents_read_as_none_not_an_exception(tmp_path):
    backend = JsonFileStore(tmp_path / "state")

    assert backend.get_mission("mission-never-existed") is None
    assert backend.get_approval("appr-never-existed") is None
    assert backend.list_missions() == []
    assert backend.list_approvals() == []
    assert backend.list_events() == []


def test_corrupt_documents_are_skipped_not_fatal(tmp_path):
    """A half-written file from a crash must not take the API down on restart."""
    state = tmp_path / "state"
    backend = JsonFileStore(state)
    good = _mission()
    backend.save_mission(good)

    (state / "missions" / "mission-truncated.json").write_text(
        '{"id": "mission-truncated", "enter', encoding="utf-8"
    )
    (state / "missions" / "mission-wrong-shape.json").write_text(
        json.dumps({"id": "mission-wrong-shape", "unexpected": True}), encoding="utf-8"
    )
    (state / "events" / f"{good.id}.jsonl").write_text(
        "not json\n" + json.dumps(
            Event(type=EventType.mission_created, missionId=good.id, summary="ok").model_dump(
                mode="json"
            ),
            default=str,
        )
        + "\n\n",
        encoding="utf-8",
    )

    assert [item.id for item in backend.list_missions()] == [good.id]
    assert backend.get_mission("mission-truncated") is None
    assert backend.get_mission("mission-wrong-shape") is None
    assert [event.type for event in backend.list_events(good.id)] == [EventType.mission_created]


def test_writes_are_atomic_and_leave_no_temp_files(tmp_path):
    state = tmp_path / "state"
    backend = JsonFileStore(state)
    mission = _mission()

    for _ in range(3):
        backend.save_mission(mission)

    assert list((state / "missions").glob("*.tmp")) == []
    assert len(list((state / "missions").glob("*.json"))) == 1


def test_purge_clears_state_but_leaves_a_usable_store(tmp_path):
    state = tmp_path / "state"
    backend = JsonFileStore(state)
    mission = _mission()
    backend.save_mission(mission)

    backend.purge()

    assert backend.list_missions() == []
    assert backend.missions_dir.is_dir()
    backend.save_mission(mission)
    assert backend.get_mission(mission.id) is not None


@pytest.mark.xfail(
    strict=False,
    reason=(
        "KNOWN PRODUCTION DEFECT (reported, not fixed here): JsonFileStore writes "
        "with the raw id (`self.missions_dir / f'{mission.id}.json'`) but reads "
        "through `_safe_name()`. Any id containing a character `_safe_name` "
        "rewrites is stored under one name and looked up under another, so it can "
        "never be read back. Latent today because ids are `mission-<hex>`."
    ),
)
def test_save_and_read_agree_on_the_file_name(tmp_path):
    backend = JsonFileStore(tmp_path / "state")
    mission = _mission(id="mission:weird id")
    approval = _approval(mission.id, id="appr:weird id")

    backend.save_mission(mission)
    backend.save_approval(approval)

    assert backend.get_mission(mission.id) is not None
    assert backend.get_approval(approval.id) is not None


@pytest.mark.xfail(
    strict=False,
    reason=(
        "KNOWN PRODUCTION DEFECT (reported, not fixed here): the write path does "
        "not sanitise the id, so a traversal id resolves outside the state "
        "directory. It currently raises OSError because the target directory does "
        "not exist, rather than being rejected or sanitised."
    ),
)
def test_path_traversal_id_cannot_escape_the_state_directory(tmp_path):
    """Ids reach the filesystem as file names, so a hostile id must not escape
    the state directory — and must not crash the write path either."""
    state = tmp_path / "state"
    backend = JsonFileStore(state)

    backend.save_mission(_mission(id="../../escaped"))

    assert not (tmp_path.parent / "escaped.json").exists()
    assert not (tmp_path / "escaped.json").exists()
    assert list((state / "missions").glob("*.json"))


# ── DualStore: cache + read-through ─────────────────────────────────────────


def test_dual_store_selects_the_file_backend_without_credentials(tmp_path):
    dual = DualStore(StoreBackend.file, tmp_path / "state")

    assert dual.backend == "file"
    assert "state" in dual.backend_note


def test_dual_store_reads_through_after_a_simulated_restart(tmp_path):
    state = tmp_path / "state"
    before = DualStore(StoreBackend.file, state)
    mission = _mission()
    approval = _approval(mission.id)
    before.save_mission(mission)
    before.save_approval(approval)
    before.save_event(
        Event(type=EventType.mission_created, missionId=mission.id, summary="created")
    )

    # A brand new process: empty cache, same durable directory.
    after = DualStore(StoreBackend.file, state)
    assert after.missions == {}, "the new process must start with a cold cache"

    recovered = after.get_mission(mission.id)
    assert recovered.id == mission.id
    assert recovered.status == MissionStatus.awaiting_approval
    assert after.get_approval(approval.id).id == approval.id
    assert [event.type for event in after.list_events(mission.id)] == [
        EventType.mission_created
    ]
    # The read-through populated the hot cache.
    assert mission.id in after.missions


def test_dual_store_rehydrate_reports_what_it_loaded(tmp_path):
    state = tmp_path / "state"
    before = DualStore(StoreBackend.file, state)
    mission = _mission()
    before.save_mission(mission)
    before.save_approval(_approval(mission.id))
    before.save_event(Event(type=EventType.mission_created, missionId=mission.id, summary="x"))

    after = DualStore(StoreBackend.file, state)
    counts = after.rehydrate()

    assert counts == {"missions": 1, "events": 1, "approvals": 1}
    assert [item.id for item in after.list_missions()] == [mission.id]


def test_dual_store_get_mission_raises_key_error_for_unknown_ids(tmp_path):
    dual = DualStore(StoreBackend.file, tmp_path / "state")

    with pytest.raises(KeyError):
        dual.get_mission("mission-does-not-exist")
    with pytest.raises(KeyError):
        dual.get_approval("appr-does-not-exist")


def test_memory_backend_has_no_durable_state(tmp_path):
    dual = DualStore(StoreBackend.memory, tmp_path / "state")
    mission = _mission()
    dual.save_mission(mission)

    assert dual.backend == "memory"
    assert not (tmp_path / "state").exists()


# ── the case that actually matters: a parked mission survives a restart ─────


async def test_a_mission_parked_on_approval_is_recoverable_after_restart(tmp_path, seeded_store):
    """End-to-end §21/§22: run a real mission until it parks on the human
    approval, then read it back from a cold store as a restarted API would."""
    state = tmp_path / "restart-state"
    store.configure(StoreBackend.file, state)
    store.reset()
    store.seed_agents_from_roster()

    mission = await mission_service.start_mission(
        StartMissionRequest(
            objective=(
                "Verify the vendor, clear sanctions and compliance, assess financial risk "
                "and configure payment terms, then prepare procurement onboarding."
            )
        )
    )
    parked = await mission_service.wait_for_mission(mission.id, 60.0)
    assert parked.status == MissionStatus.awaiting_approval
    approval_id = parked.awaitingApprovalId
    assert approval_id is not None
    event_count = len(store.list_events(mission.id))
    assert event_count > 0

    # Simulate the API process restarting: brand new store over the same files.
    restarted = DualStore(StoreBackend.file, state)
    counts = restarted.rehydrate()

    assert counts["missions"] >= 1
    assert counts["approvals"] >= 1
    assert counts["events"] == event_count

    recovered = restarted.get_mission(mission.id)
    assert recovered.id == mission.id
    assert recovered.status == MissionStatus.awaiting_approval
    assert recovered.awaitingApprovalId == approval_id
    assert recovered.planSource == PlanSource.deterministic_fallback
    assert recovered.planModel is None

    finance = recovered.task_by_id("task-finance")
    assert finance.status == TaskStatus.blocked
    assert finance.pendingTool == "create_payment"
    assert finance.awaitingApprovalId == approval_id
    assert set(finance.result) == {"financial_lookup", "risk_calculator"}, (
        "tool results captured before the park did not survive persistence"
    )
    assert recovered.task_by_id("task-research").status == TaskStatus.completed
    assert recovered.task_by_id("task-compliance").status == TaskStatus.completed
    assert "task-research" in recovered.results

    recovered_approval = restarted.get_approval(approval_id)
    assert recovered_approval.status == ApprovalStatus.pending
    assert recovered_approval.tool == "create_payment"
    assert recovered_approval.taskId == "task-finance"

    types = [event.type for event in restarted.list_events(mission.id)]
    assert EventType.mission_created in types
    assert EventType.plan_created in types
    assert EventType.approval_requested in types
    assert EventType.security_alert in types


async def test_events_written_during_a_mission_are_all_on_disk(tmp_path, seeded_store):
    """The audit log is the product. Nothing may be memory-only."""
    state = tmp_path / "audit-state"
    store.configure(StoreBackend.file, state)
    store.reset()
    store.seed_agents_from_roster()

    mission = await mission_service.start_mission(StartMissionRequest())
    await mission_service.wait_for_mission(mission.id, 60.0)

    in_memory = store.list_events(mission.id)
    on_disk = JsonFileStore(state).list_events(mission.id)

    assert len(on_disk) == len(in_memory)
    assert [event.id for event in on_disk] == [event.id for event in in_memory]
