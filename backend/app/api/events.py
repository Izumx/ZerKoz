import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.events import bus

router = APIRouter(tags=["events"])
HEARTBEAT_SECONDS = 15


@router.get("/events/stream")
async def stream(request: Request) -> StreamingResponse:
    async def generate():
        with bus.subscription() as sub:
            yield "retry: 3000\n\n"
            while not await request.is_disconnected():
                message = await sub.get(timeout=HEARTBEAT_SECONDS)
                if message is None:
                    yield ": ping\n\n"
                else:
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
