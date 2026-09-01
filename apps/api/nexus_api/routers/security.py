from fastapi import APIRouter

from nexus_api.schemas.domain import EventType
from nexus_api.services.storage import store

router = APIRouter(prefix="/api/security", tags=["security"])


@router.get("/alerts")
async def list_security_alerts() -> list[dict]:
    return [
        event.model_dump(mode="json")
        for event in store.list_events()
        if event.type == EventType.security_alert
    ]

