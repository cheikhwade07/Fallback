import asyncio
import json
import logging
from collections import deque
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    event_type: Literal["FALL_DETECTED", "HEARTBEAT", "RECOVERED"]
    x: float
    y: float
    fall_duration: float
    latency_ms: float
    timestamp: str
    frame_b64: str


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("uvicorn.error")
recent_events: deque[dict] = deque(maxlen=50)
latest_event: dict | None = None
subscribers: set[asyncio.Queue[dict]] = set()


@app.post("/api/event")
async def receive_event(event: Event) -> dict:
    global latest_event

    payload = event.model_dump()
    latest_event = payload
    recent_events.append(payload)
    logger.info(
        "event_type=%s x=%s y=%s latency_ms=%s frame_b64_length=%d",
        event.event_type,
        event.x,
        event.y,
        event.latency_ms,
        len(event.frame_b64),
    )

    for queue in tuple(subscribers):
        queue.put_nowait(payload)

    return {"ok": True}


@app.get("/api/stream")
async def stream_events(request: Request) -> StreamingResponse:
    async def event_stream():
        queue: asyncio.Queue[dict] = asyncio.Queue()
        subscribers.add(queue)
        try:
            if latest_event is not None:
                yield f"data: {json.dumps(latest_event)}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ":keepalive\n\n"
        finally:
            subscribers.discard(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/events")
async def get_events() -> list[dict]:
    return list(recent_events)


@app.get("/api/health")
async def health() -> dict[str, bool]:
    return {"ok": True}
