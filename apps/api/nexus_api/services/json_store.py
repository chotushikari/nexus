"""Local JSON-file persistence.

This is the fallback that makes NEXUS survive an API restart with no GCP
credentials at all, which is what §21 ("refresh browser, mission state remains")
and §22 ("browser closes, backend state survives") actually require locally.

Layout under the state directory (gitignored, default `.nexus-state/`):

    missions/<missionId>.json
    approvals/<approvalId>.json
    events/<missionId>.jsonl      # append-only audit log, one JSON object/line

Writes are atomic (temp file + `os.replace`) for documents, and append-only for
the event log, so a crash mid-write cannot corrupt an existing document.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from threading import RLock

from pydantic import ValidationError

from nexus_api.core.logging import get_logger
from nexus_api.schemas.domain import Approval, ApprovalStatus, Event, Mission

logger = get_logger("json_store")


class JsonFileStore:
    """Durable document store backed by the local filesystem."""

    backend_name = "file"

    def __init__(self, base_dir: Path | str) -> None:
        self.base = Path(base_dir)
        self.missions_dir = self.base / "missions"
        self.approvals_dir = self.base / "approvals"
        self.events_dir = self.base / "events"
        self._lock = RLock()
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for directory in (self.missions_dir, self.approvals_dir, self.events_dir):
            directory.mkdir(parents=True, exist_ok=True)

    # ── writes ──────────────────────────────────────────────────────────────

    def _atomic_write(self, path: Path, payload: dict) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, path)

    def save_mission(self, mission: Mission) -> None:
        with self._lock:
            self._ensure_dirs()
            self._atomic_write(
                self.missions_dir / f"{mission.id}.json", mission.model_dump(mode="json")
            )

    def save_approval(self, approval: Approval) -> None:
        with self._lock:
            self._ensure_dirs()
            self._atomic_write(
                self.approvals_dir / f"{approval.id}.json", approval.model_dump(mode="json")
            )

    def save_event(self, event: Event) -> None:
        with self._lock:
            self._ensure_dirs()
            path = self.events_dir / f"{_safe_name(event.missionId)}.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.model_dump(mode="json"), default=str) + "\n")

    def save_agent(self, agent) -> None:  # noqa: ANN001 - roster is source of truth
        """Agents are seeded from `data/agents/roster.json`; nothing to persist."""
        return None

    # ── reads ───────────────────────────────────────────────────────────────

    def get_mission(self, mission_id: str) -> Mission | None:
        path = self.missions_dir / f"{_safe_name(mission_id)}.json"
        payload = _read_json(path)
        if payload is None:
            return None
        return _validate(Mission, payload, path)

    def list_missions(self) -> list[Mission]:
        missions: list[Mission] = []
        if not self.missions_dir.exists():
            return missions
        for path in sorted(self.missions_dir.glob("*.json")):
            payload = _read_json(path)
            if payload is None:
                continue
            mission = _validate(Mission, payload, path)
            if mission is not None:
                missions.append(mission)
        return sorted(missions, key=lambda m: m.createdAt)

    def get_approval(self, approval_id: str) -> Approval | None:
        path = self.approvals_dir / f"{_safe_name(approval_id)}.json"
        payload = _read_json(path)
        if payload is None:
            return None
        return _validate(Approval, payload, path)

    def list_approvals(self, status: ApprovalStatus | None = None) -> list[Approval]:
        approvals: list[Approval] = []
        if not self.approvals_dir.exists():
            return approvals
        for path in sorted(self.approvals_dir.glob("*.json")):
            payload = _read_json(path)
            if payload is None:
                continue
            approval = _validate(Approval, payload, path)
            if approval is not None and (status is None or approval.status == status):
                approvals.append(approval)
        return sorted(approvals, key=lambda a: a.createdAt)

    def list_events(self, mission_id: str | None = None) -> list[Event]:
        if not self.events_dir.exists():
            return []
        if mission_id:
            paths = [self.events_dir / f"{_safe_name(mission_id)}.jsonl"]
        else:
            paths = sorted(self.events_dir.glob("*.jsonl"))

        seen: set[str] = set()
        events: list[Event] = []
        for path in paths:
            if not path.exists():
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError as exc:
                logger.warning("json_store.event_log_unreadable", path=str(path), reason=str(exc))
                continue
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "json_store.event_line_corrupt", path=str(path), reason=str(exc)
                    )
                    continue
                event = _validate(Event, payload, path)
                if event is None or event.id in seen:
                    continue
                seen.add(event.id)
                events.append(event)
        return sorted(events, key=lambda e: e.timestamp)

    # ── maintenance ─────────────────────────────────────────────────────────

    def purge(self) -> None:
        """Delete all persisted state. Only ever called by an explicit demo reset."""
        with self._lock:
            if self.base.exists():
                shutil.rmtree(self.base, ignore_errors=True)
            self._ensure_dirs()
        logger.info("json_store.purged", path=str(self.base))


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)


def _read_json(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("json_store.unreadable", path=str(path), reason=str(exc))
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("json_store.corrupt", path=str(path), reason=str(exc))
        return None
    return payload if isinstance(payload, dict) else None


def _validate(model, payload: dict, path: Path):  # noqa: ANN001, ANN202
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        logger.warning(
            "json_store.schema_mismatch",
            path=str(path),
            model=model.__name__,
            reason=str(exc),
        )
        return None
