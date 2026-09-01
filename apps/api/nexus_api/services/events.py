from typing import Any

from nexus_api.schemas.domain import Event, EventType
from nexus_api.services.storage import store


class EventBus:
    def emit(
        self,
        event_type: EventType,
        mission_id: str,
        summary: str,
        agent_id: str | None = None,
        target_agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Event:
        event = Event(
            type=event_type,
            missionId=mission_id,
            agentId=agent_id,
            targetAgentId=target_agent_id,
            summary=summary,
            metadata=metadata or {},
        )
        return store.save_event(event)


event_bus = EventBus()

