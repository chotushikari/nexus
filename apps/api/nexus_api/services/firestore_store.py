"""Firestore persistence adapter — read *and* write.

Previously this adapter was write-only, which meant nothing could ever be
rehydrated from Firestore. The read path below is what `DualStore` calls on a
cache miss, so a mission created before a restart can be reopened.

`google-cloud-firestore` is an optional dependency: the constructor raises
`FirestoreUnavailableError` when the SDK or credentials are missing, and
`DualStore` then falls back to the local JSON store.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import ValidationError

from nexus_api.core.logging import get_logger
from nexus_api.schemas.domain import AgentCard, Approval, ApprovalStatus, Event, Mission

logger = get_logger("firestore")


class FirestoreUnavailableError(RuntimeError):
    """Raised when a Firestore client cannot be constructed."""


class PersistenceStore(Protocol):
    def save_agent(self, agent: AgentCard) -> None: ...

    def save_mission(self, mission: Mission) -> None: ...

    def save_event(self, event: Event) -> None: ...

    def save_approval(self, approval: Approval) -> None: ...

    def get_mission(self, mission_id: str) -> Mission | None: ...

    def list_missions(self) -> list[Mission]: ...

    def list_events(self, mission_id: str | None = None) -> list[Event]: ...

    def list_approvals(self, status: ApprovalStatus | None = None) -> list[Approval]: ...


class FirestoreStore:
    """Firestore-backed implementation of `PersistenceStore`."""

    backend_name = "firestore"

    def __init__(self, project: str, database: str = "(default)") -> None:
        try:
            from google.cloud import firestore
        except ImportError as exc:
            raise FirestoreUnavailableError(
                f"google-cloud-firestore is not installed: {exc}"
            ) from exc

        try:
            from google.auth.exceptions import GoogleAuthError

            self.client = firestore.Client(project=project, database=database)
        except (OSError, ValueError, RuntimeError, GoogleAuthError) as exc:
            # GoogleAuthError covers DefaultCredentialsError (no ADC), which
            # is *not* a subclass of the other three — without it, `auto`
            # store selection crashes startup instead of degrading.
            raise FirestoreUnavailableError(f"firestore client init failed: {exc}") from exc

        self.project = project
        self.database = database

    # ── writes ──────────────────────────────────────────────────────────────

    def save_agent(self, agent: AgentCard) -> None:
        self._set("agents", agent.id, agent.model_dump(mode="json"))

    def save_mission(self, mission: Mission) -> None:
        self._set("missions", mission.id, mission.model_dump(mode="json"))

    def save_event(self, event: Event) -> None:
        self._set("events", event.id, event.model_dump(mode="json"))

    def save_approval(self, approval: Approval) -> None:
        self._set("approvals", approval.id, approval.model_dump(mode="json"))

    def _set(self, collection: str, document_id: str, payload: dict[str, Any]) -> None:
        try:
            self.client.collection(collection).document(document_id).set(payload)
        except (OSError, RuntimeError, ValueError) as exc:
            logger.error(
                "firestore.write_failed",
                collection=collection,
                documentId=document_id,
                reason=str(exc),
            )

    # ── reads ───────────────────────────────────────────────────────────────

    def get_mission(self, mission_id: str) -> Mission | None:
        payload = self._get("missions", mission_id)
        return _validate(Mission, payload) if payload else None

    def list_missions(self) -> list[Mission]:
        missions = [
            model
            for model in (_validate(Mission, doc) for doc in self._stream("missions"))
            if model is not None
        ]
        return sorted(missions, key=lambda m: m.createdAt)

    def list_events(self, mission_id: str | None = None) -> list[Event]:
        docs = self._stream("events", ("missionId", "==", mission_id) if mission_id else None)
        events = [
            model for model in (_validate(Event, doc) for doc in docs) if model is not None
        ]
        return sorted(events, key=lambda e: e.timestamp)

    def get_approval(self, approval_id: str) -> Approval | None:
        payload = self._get("approvals", approval_id)
        return _validate(Approval, payload) if payload else None

    def list_approvals(self, status: ApprovalStatus | None = None) -> list[Approval]:
        where = ("status", "==", status.value) if status else None
        docs = self._stream("approvals", where)
        approvals = [
            model for model in (_validate(Approval, doc) for doc in docs) if model is not None
        ]
        return sorted(approvals, key=lambda a: a.createdAt)

    def _get(self, collection: str, document_id: str) -> dict[str, Any] | None:
        try:
            snapshot = self.client.collection(collection).document(document_id).get()
        except (OSError, RuntimeError, ValueError) as exc:
            logger.error(
                "firestore.read_failed",
                collection=collection,
                documentId=document_id,
                reason=str(exc),
            )
            return None
        if not getattr(snapshot, "exists", False):
            return None
        return snapshot.to_dict()

    def _stream(
        self, collection: str, where: tuple[str, str, Any] | None = None
    ) -> list[dict[str, Any]]:
        try:
            query = self.client.collection(collection)
            if where is not None:
                field, op, value = where
                query = query.where(filter=_field_filter(field, op, value))
            return [doc.to_dict() for doc in query.stream()]
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            logger.error("firestore.query_failed", collection=collection, reason=str(exc))
            return []


def _field_filter(field: str, op: str, value: Any):  # noqa: ANN202
    from google.cloud.firestore_v1.base_query import FieldFilter

    return FieldFilter(field, op, value)


def _validate(model, payload: dict[str, Any] | None):  # noqa: ANN001, ANN202
    if not payload:
        return None
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        logger.warning("firestore.schema_mismatch", model=model.__name__, reason=str(exc))
        return None


def firestore_collections() -> list[str]:
    return [
        "enterprises",
        "departments",
        "agents",
        "missions",
        "tasks",
        "messages",
        "events",
        "policies",
        "approvals",
        "memory",
        "tools",
    ]
