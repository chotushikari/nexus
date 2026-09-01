from fastapi import APIRouter

from nexus_api.services.mission import mission_service

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/seed")
async def seed_demo() -> dict[str, object]:
    return mission_service.seed_demo()


@router.post("/reset")
async def reset_demo() -> dict[str, object]:
    return mission_service.seed_demo()

