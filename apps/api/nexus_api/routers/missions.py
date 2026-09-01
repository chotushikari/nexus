from fastapi import APIRouter, HTTPException

from nexus_api.schemas.domain import Mission, StartMissionRequest
from nexus_api.services.mission import mission_service
from nexus_api.services.storage import store

router = APIRouter(prefix="/api/missions", tags=["missions"])


@router.post("", response_model=Mission, status_code=202)
async def start_mission(request: StartMissionRequest) -> Mission:
    """Create a mission and return immediately.

    Planning and execution run in a background task on the server (§22), so the
    response is a `created` mission. Watch `/api/events/stream` for progress and
    re-read `GET /api/missions/{id}` for state.
    """
    return await mission_service.start_mission(request)


@router.get("", response_model=list[Mission])
async def list_missions() -> list[Mission]:
    return store.list_missions()


@router.get("/{mission_id}", response_model=Mission)
async def get_mission(mission_id: str) -> Mission:
    try:
        return store.get_mission(mission_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="mission not found") from exc


@router.get("/{mission_id}/events")
async def get_events(mission_id: str) -> list[dict]:
    return [event.model_dump(mode="json") for event in store.list_events(mission_id)]


@router.get("/{mission_id}/audit")
async def get_audit(mission_id: str) -> dict[str, object]:
    try:
        mission = store.get_mission(mission_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="mission not found") from exc
    return {
        "mission": mission.model_dump(mode="json"),
        "events": [event.model_dump(mode="json") for event in store.list_events(mission_id)],
    }
