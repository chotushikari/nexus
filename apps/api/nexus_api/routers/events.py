import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from nexus_api.schemas.domain import Event
from nexus_api.services.storage import store

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=list[Event])
async def list_events(mission_id: str | None = None) -> list[Event]:
    return store.list_events(mission_id)


@router.get("/stream")
async def stream_events(request: Request, mission_id: str | None = None):
    """
    Server-Sent Events endpoint.
    Frontend connects once and receives all new events as they arrive.
    Replaces 3-second polling for the Visual Office live updates.
    """

    async def generator():
        # SSE comment bytes must flow immediately: Cloud Run's proxy buffers
        # the response head until the first body byte, and with an empty
        # event store nothing was flushed — EventSource hung forever.
        yield ": connected\n\n"

        # Send any already-existing events immediately on connect
        snapshot = store.list_events(mission_id)
        for ev in snapshot:
            yield f"data: {ev.model_dump_json()}\n\n"

        last_count = len(snapshot)
        loop = asyncio.get_event_loop()
        last_beat = loop.time()

        # Then stream new events as they arrive
        while True:
            if await request.is_disconnected():
                break
            events = store.list_events(mission_id)
            new_events = events[last_count:]
            for ev in new_events:
                yield f"data: {ev.model_dump_json()}\n\n"
            last_count = len(events)
            if loop.time() - last_beat > 15.0:
                # Comment-only keepalive; EventSource ignores it, proxies don't.
                yield ": ping\n\n"
                last_beat = loop.time()
            await asyncio.sleep(0.4)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",      # disable nginx buffering
            "Connection": "keep-alive",
        },
    )
