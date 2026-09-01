"""Persistence for NEXUS.

Three layers, one interface:

  * `InMemoryStore` – hot cache, always present.
  * `JsonFileStore` – durable local files (`.nexus-state/`, gitignored). No
    credentials required, survives an API restart.
  * `FirestoreStore` – durable cloud store when credentials exist.

`DualStore` writes through to the selected durable backend and *reads through*
it on a cache miss, so mission state genuinely survives a process restart. The
choice is resolved once, logged at startup, and reported on `/api/health`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock

from nexus_api.core.config import StoreBackend, settings
from nexus_api.core.logging import get_logger
from nexus_api.schemas.domain import AgentCard, Approval, ApprovalStatus, Event, Mission, utc_now
from nexus_api.services.capabilities import capabilities
from nexus_api.services.json_store import JsonFileStore

logger = get_logger("storage")


def find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "data").exists():
            return parent
    return current.parents[2]


PROJECT_ROOT = find_project_root()
DATA_DIR = Path(os.environ.get("NEXUS_DATA_DIR", PROJECT_ROOT / "data"))


def resolve_state_dir(state_dir: str | Path | None = None) -> Path:
    raw = state_dir or os.environ.get("NEXUS_STATE_DIR") or settings.nexus_state_dir
    path = Path(raw)
    return path if path.is_absolute() else (PROJECT_ROOT / path)


class InMemoryStore:
    """Deterministic in-process store with a Firestore-shaped boundary."""

    backend_name = "memory"

    def __init__(self) -> None:
        self._lock = RLock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.agents: dict[str, AgentCard] = {}
            self.missions: dict[str, Mission] = {}
            self.events: dict[str, Event] = {}
            self.approvals: dict[str, Approval] = {}
            self.memory: dict[str, dict] = {}

    def seed_agents_from_roster(self) -> list[AgentCard]:
        roster_path = DATA_DIR / "agents" / "roster.json"
        payload = json.loads(roster_path.read_text(encoding="utf-8"))
        agents = [AgentCard.model_validate(item) for item in payload["agents"]]
        with self._lock:
            self.agents = {agent.id: agent for agent in agents}
        return agents

    def get_agent(self, agent_id: str) -> AgentCard:
        return self.agents[agent_id]

    def list_agents(self) -> list[AgentCard]:
        return sorted(self.agents.values(), key=lambda a: (a.tier.value, a.name))

    def save_mission(self, mission: Mission) -> Mission:
        mission.updatedAt = utc_now()
        with self._lock:
            self.missions[mission.id] = mission
        return mission

    def get_mission(self, mission_id: str) -> Mission:
        return self.missions[mission_id]

    def list_missions(self) -> list[Mission]:
        return sorted(self.missions.values(), key=lambda m: m.createdAt)

    def save_event(self, event: Event) -> Event:
        with self._lock:
            self.events[event.id] = event
        return event

    def list_events(self, mission_id: str | None = None) -> list[Event]:
        events = list(self.events.values())
        if mission_id:
            events = [e for e in events if e.missionId == mission_id]
        return sorted(events, key=lambda e: e.timestamp)

    def save_approval(self, approval: Approval) -> Approval:
        with self._lock:
            self.approvals[approval.id] = approval
        return approval

    def get_approval(self, approval_id: str) -> Approval:
        return self.approvals[approval_id]

    def list_approvals(self, status: ApprovalStatus | None = None) -> list[Approval]:
        approvals = list(self.approvals.values())
        if status:
            approvals = [a for a in approvals if a.status == status]
        return sorted(approvals, key=lambda a: a.createdAt)


class DualStore:
    """In-memory cache in front of a durable backend, with read-through."""

    def __init__(
        self,
        backend: StoreBackend | None = None,
        state_dir: str | Path | None = None,
    ) -> None:
        self._mem = InMemoryStore()
        self._durable = None
        self._backend_name = "memory"
        self._backend_note = ""
        self._rehydrated = True
        self.configure(backend, state_dir)

    # ── backend selection ───────────────────────────────────────────────────

    def configure(
        self,
        backend: StoreBackend | None = None,
        state_dir: str | Path | None = None,
    ) -> str:
        """(Re)resolve the durable backend. Returns the backend name."""
        requested = backend or settings.store_backend
        self._durable = None
        self._backend_name = "memory"
        self._backend_note = ""

        if requested == StoreBackend.memory:
            self._backend_note = "explicitly configured as in-memory only"
        else:
            if requested in (StoreBackend.auto, StoreBackend.firestore):
                self._try_firestore(required=requested == StoreBackend.firestore)
            if self._durable is None and requested != StoreBackend.firestore:
                self._use_file_store(state_dir)
            elif self._durable is None:
                self._use_file_store(state_dir)

        self._rehydrated = self._durable is None
        logger.info(
            "store.selected",
            backend=self._backend_name,
            requested=requested.value,
            note=self._backend_note,
            stateDir=str(getattr(self._durable, "base", "")) or None,
        )
        capabilities.note("store_backend", self._backend_name)
        capabilities.note("store_note", self._backend_note)
        return self._backend_name

    def _try_firestore(self, required: bool) -> None:
        from nexus_api.services.firestore_store import (
            FirestoreStore,
            FirestoreUnavailableError,
        )

        if not settings.google_cloud_project:
            self._backend_note = "no GOOGLE_CLOUD_PROJECT configured"
            return
        try:
            self._durable = FirestoreStore(
                project=settings.google_cloud_project, database=settings.firestore_database
            )
        except FirestoreUnavailableError as exc:
            self._backend_note = f"firestore unavailable: {exc}"
            capabilities.record_failure("firestore", str(exc))
            level = logger.error if required else logger.warning
            level("store.firestore_unavailable", reason=str(exc), required=required)
            return
        self._backend_name = "firestore"
        self._backend_note = (
            f"project={settings.google_cloud_project} database={settings.firestore_database}"
        )
        capabilities.record_success("firestore", self._backend_note)

    def _use_file_store(self, state_dir: str | Path | None) -> None:
        path = resolve_state_dir(state_dir)
        try:
            self._durable = JsonFileStore(path)
        except OSError as exc:
            self._backend_note = f"file store unavailable at {path}: {exc}"
            logger.error("store.file_unavailable", path=str(path), reason=str(exc))
            return
        self._backend_name = "file"
        if not self._backend_note:
            self._backend_note = f"local JSON state at {path}"
        else:
            self._backend_note = f"{self._backend_note}; fell back to local JSON state at {path}"

    @property
    def backend(self) -> str:
        return self._backend_name

    @property
    def backend_note(self) -> str:
        return self._backend_note

    # ── attribute delegation for the in-memory dictionaries ─────────────────

    def __getattr__(self, name: str):
        return getattr(self._mem, name)

    # ── rehydration ─────────────────────────────────────────────────────────

    def rehydrate(self) -> dict[str, int]:
        """Load durable state into the cache. Idempotent; safe at startup."""
        if self._durable is None:
            self._rehydrated = True
            return {"missions": 0, "events": 0, "approvals": 0}

        missions = self._durable.list_missions()
        approvals = self._durable.list_approvals()
        events = self._durable.list_events()
        for mission in missions:
            self._mem.missions.setdefault(mission.id, mission)
        for approval in approvals:
            self._mem.approvals.setdefault(approval.id, approval)
        for event in events:
            self._mem.events.setdefault(event.id, event)
        self._rehydrated = True
        counts = {"missions": len(missions), "events": len(events), "approvals": len(approvals)}
        logger.info("store.rehydrated", backend=self._backend_name, **counts)
        return counts

    def _ensure_rehydrated(self) -> None:
        if not self._rehydrated:
            self.rehydrate()

    # ── lifecycle ───────────────────────────────────────────────────────────

    def reset(self, purge_durable: bool = True) -> None:
        """Reset the demo. Clears the cache and (for the local file backend)
        the durable state as well. Firestore is never bulk-deleted."""
        self._mem.reset()
        if purge_durable and self._durable is not None and hasattr(self._durable, "purge"):
            self._durable.purge()
        self._rehydrated = self._durable is None
        logger.info("store.reset", backend=self._backend_name, purgedDurable=purge_durable)

    # ── agents (roster is the source of truth; not persisted) ───────────────

    def seed_agents_from_roster(self) -> list[AgentCard]:
        return self._mem.seed_agents_from_roster()

    def get_agent(self, agent_id: str) -> AgentCard:
        return self._mem.get_agent(agent_id)

    def list_agents(self) -> list[AgentCard]:
        return self._mem.list_agents()

    # ── missions ────────────────────────────────────────────────────────────

    def save_mission(self, mission: Mission) -> Mission:
        mission = self._mem.save_mission(mission)
        if self._durable is not None:
            self._durable.save_mission(mission)
        return mission

    def get_mission(self, mission_id: str) -> Mission:
        try:
            return self._mem.get_mission(mission_id)
        except KeyError:
            pass
        if self._durable is None:
            raise KeyError(mission_id)
        mission = self._durable.get_mission(mission_id)
        if mission is None:
            raise KeyError(mission_id)
        logger.info(
            "store.mission_rehydrated", missionId=mission_id, backend=self._backend_name
        )
        self._mem.missions[mission.id] = mission
        return mission

    def list_missions(self) -> list[Mission]:
        self._ensure_rehydrated()
        return self._mem.list_missions()

    # ── events ──────────────────────────────────────────────────────────────

    def save_event(self, event: Event) -> Event:
        event = self._mem.save_event(event)
        if self._durable is not None:
            self._durable.save_event(event)
        return event

    def list_events(self, mission_id: str | None = None) -> list[Event]:
        cached = self._mem.list_events(mission_id)
        if cached or self._durable is None:
            return cached
        durable = self._durable.list_events(mission_id)
        for event in durable:
            self._mem.events.setdefault(event.id, event)
        if durable:
            logger.info(
                "store.events_rehydrated",
                missionId=mission_id,
                count=len(durable),
                backend=self._backend_name,
            )
        return self._mem.list_events(mission_id)

    # ── approvals ───────────────────────────────────────────────────────────

    def save_approval(self, approval: Approval) -> Approval:
        approval = self._mem.save_approval(approval)
        if self._durable is not None:
            self._durable.save_approval(approval)
        return approval

    def get_approval(self, approval_id: str) -> Approval:
        try:
            return self._mem.get_approval(approval_id)
        except KeyError:
            pass
        if self._durable is None:
            raise KeyError(approval_id)
        getter = getattr(self._durable, "get_approval", None)
        approval = getter(approval_id) if getter else None
        if approval is None:
            raise KeyError(approval_id)
        self._mem.approvals[approval.id] = approval
        return approval

    def list_approvals(self, status: ApprovalStatus | None = None) -> list[Approval]:
        self._ensure_rehydrated()
        return self._mem.list_approvals(status)


# Export a singleton used throughout the codebase.
store = DualStore()


def configure_store(
    backend: StoreBackend | str | None = None, state_dir: str | Path | None = None
) -> str:
    """Reconfigure the global store. Used by tests and by startup wiring."""
    if isinstance(backend, str):
        backend = StoreBackend(backend)
    return store.configure(backend, state_dir)
