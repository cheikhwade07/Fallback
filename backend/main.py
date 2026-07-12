import asyncio
import json
import logging
import os
import re
from collections import deque
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal
from urllib import request

from dotenv import load_dotenv
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


load_dotenv(Path(__file__).resolve().parent.parent / ".env")

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_TIMEOUT_SECONDS = 3.0
SYSTEM_PROMPT = """You are the dispatch voice for an automated worker-safety system on a construction site. A fall has been confirmed. You are briefing the responder who is about to enter.
You receive (a) an annotated camera frame captured at the moment of detection, and (b) a JSON object of measured facts.
Output EXACTLY three sentences, spoken aloud over a radio. Urgent, clipped, professional. No preamble, no markdown.
Sentence 1: The situation and the clock — where the worker is, how long they have been down.
Sentence 2: What is VISIBLE in the frame — the worker's body position and orientation, and whether anything obstructs the view of them.
Sentence 3: How to reach them from the entrance, and what to get around.
WHAT YOU MAY SAY ABOUT THE IMAGE — visible physical facts only:

Body position: prone, supine, on their side, curled, sprawled, limbs extended.
Orientation relative to the camera or to objects in the frame.
Whether the worker is partially hidden by an object.
Whether the worker is fully or partially in view.

WHAT YOU MUST NEVER SAY — you CANNOT see these things and stating them would be a fabricated medical assessment given to a first responder:

Consciousness, responsiveness, or alertness.
Injuries, bleeding, fractures, trauma, or pain.
Breathing, pulse, or any vital sign.
The cause of the fall.
The worker's identity, age, or condition.
Anything you are inferring rather than observing.

If you cannot see the worker clearly in the frame, say exactly that — "visual is partially obstructed" — and do not speculate.
OTHER HARD CONSTRAINTS:

Every number you state must appear in the JSON.
NEVER mention hardware — no GPIO, klaxon, siren, or physical output.
Say "metres," not "m." Round the way a person speaks: "just over five seconds," "about two metres." Never read out decimals."""
FALLBACK_TEMPLATE = "Worker down at ({x}, {y}) metres, node {node_id}. Down {fall_duration} seconds. Route from entrance: {route_length} metres."

SITE_PAYLOAD = {
    "bounds_m": [[0, 0], [2, 2]],
    "entrance_m": [2.0, 0.0],
    "obstacles_m": [
        {"label": "BOX 01", "x0": 0.35, "y0": 0.375, "x1": 0.65, "y1": 0.625},
        {"label": "BOX 02", "x0": 1.35, "y0": 1.375, "x1": 1.65, "y1": 1.625},
    ],
}

# These constants mirror the existing frontend route geometry; the frontend route
# implementation remains unchanged and continues to draw the responder path.
CELL_SIZE = 0.05
GRID_SIZE = 40
OBSTACLE_INFLATION = 0.15
OBSTACLES = SITE_PAYLOAD["obstacles_m"]


def _cell(point: tuple[float, float]) -> tuple[int, int]:
    return (
        max(0, min(GRID_SIZE - 1, int(point[0] / CELL_SIZE))),
        max(0, min(GRID_SIZE - 1, int(point[1] / CELL_SIZE))),
    )


def _point(cell: tuple[int, int]) -> tuple[float, float]:
    return ((cell[0] + 0.5) * CELL_SIZE, (cell[1] + 0.5) * CELL_SIZE)


def _blocked(cell: tuple[int, int]) -> bool:
    x, y = _point(cell)
    return any(
        x >= obstacle["x0"] - OBSTACLE_INFLATION
        and x <= obstacle["x1"] + OBSTACLE_INFLATION
        and y >= obstacle["y0"] - OBSTACLE_INFLATION
        and y <= obstacle["y1"] + OBSTACLE_INFLATION
        for obstacle in OBSTACLES
    )


def _nearest_free(origin: tuple[int, int]) -> tuple[int, int] | None:
    free = [
        (col, row)
        for row in range(GRID_SIZE)
        for col in range(GRID_SIZE)
        if not _blocked((col, row))
    ]
    return min(free, key=lambda candidate: (candidate[0] - origin[0]) ** 2 + (candidate[1] - origin[1]) ** 2) if free else None


def _astar(start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]] | None:
    directions = [
        (col, row)
        for row in (-1, 0, 1)
        for col in (-1, 0, 1)
        if col or row
    ]
    open_cells = [start]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score = {start: 0.0}
    f_score = {start: ((start[0] - goal[0]) ** 2 + (start[1] - goal[1]) ** 2) ** 0.5}

    while open_cells:
        current = min(open_cells, key=lambda cell: f_score.get(cell, float("inf")))
        open_cells.remove(current)
        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.insert(0, current)
            return path

        for col_delta, row_delta in directions:
            next_cell = (current[0] + col_delta, current[1] + row_delta)
            if not (0 <= next_cell[0] < GRID_SIZE and 0 <= next_cell[1] < GRID_SIZE) or _blocked(next_cell):
                continue
            if col_delta and row_delta and (_blocked((current[0] + col_delta, current[1])) or _blocked((current[0], current[1] + row_delta))):
                continue
            step = (col_delta * col_delta + row_delta * row_delta) ** 0.5
            tentative = g_score[current] + step
            if tentative < g_score.get(next_cell, float("inf")):
                came_from[next_cell] = current
                g_score[next_cell] = tentative
                f_score[next_cell] = tentative + ((next_cell[0] - goal[0]) ** 2 + (next_cell[1] - goal[1]) ** 2) ** 0.5
                if next_cell not in open_cells:
                    open_cells.append(next_cell)
    return None


def _smooth(cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if len(cells) < 3:
        return cells
    result = [cells[0]]
    for index in range(1, len(cells) - 1):
        before, current, after = cells[index - 1], cells[index], cells[index + 1]
        if (current[0] - before[0]) * (after[1] - current[1]) != (current[1] - before[1]) * (after[0] - current[0]):
            result.append(current)
    result.append(cells[-1])
    return result


def responder_route(worker: tuple[float, float]) -> tuple[float, list[list[float]]]:
    entrance = (2.0, 0.0)
    start = _nearest_free(_cell(entrance))
    target_cell = _cell(worker)
    worker_is_valid = 0 <= worker[0] <= 2 and 0 <= worker[1] <= 2 and not _blocked(target_cell)
    target = worker if worker_is_valid else (_point(_nearest_free(target_cell)) if _nearest_free(target_cell) else entrance)
    cells = _astar(start, _nearest_free(target_cell)) if start and _nearest_free(target_cell) else None
    points = [entrance]
    if cells:
        points.extend(list(map(_point, _smooth(cells)))[1:])
        points.append(target)
    elif target != entrance:
        points.append(target)
    length = sum(
        ((after[0] - before[0]) ** 2 + (after[1] - before[1]) ** 2) ** 0.5
        for before, after in zip(points, points[1:])
    )
    return round(length, 3), [[round(x, 3), round(y, 3)] for x, y in points]


def gemini_payload(event: Event) -> dict:
    route_length, waypoints = responder_route((event.x, event.y))
    return {
        "event": {
            "node_id": event.node_id,
            "x": round(event.x, 2),
            "y": round(event.y, 2),
            "fall_duration_s": round(event.fall_duration, 1),
            "latency_ms": round(event.latency_ms, 1),
            "timestamp": event.timestamp,
        },
        "site": SITE_PAYLOAD,
        "route": {
            "length_m": round(route_length, 1),
            "waypoints_m": [[round(x, 2), round(y, 2)] for x, y in waypoints],
        },
    }


def fallback_briefing(payload: dict) -> str:
    event = payload["event"]
    route = payload["route"]
    return FALLBACK_TEMPLATE.format(
        x=event["x"],
        y=event["y"],
        node_id=event["node_id"],
        fall_duration=event["fall_duration_s"],
        route_length=route["length_m"],
    )


def _number_is_present(value: float, text: str) -> bool:
    expected = Decimal(str(value))
    for token in re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?", text):
        try:
            if Decimal(token) == expected:
                return True
        except InvalidOperation:
            continue
    return False


def _valid_briefing(text: object, payload: dict) -> str:
    if not isinstance(text, str):
        raise ValueError("Gemini response did not contain text")
    briefing = text.strip()
    if not briefing or "```" in briefing:
        raise ValueError("Gemini response was empty or markdown-wrapped")
    if len(re.findall(r"[^.!?]+(?:[.!?](?=\s|$)|$)", briefing)) != 3:
        raise ValueError("Gemini response did not contain exactly three sentences")
    if any(term in briefing.casefold() for term in ("gpio", "klaxon", "siren", "alarm", "physical output", "hardware")):
        raise ValueError("Gemini response mentioned hardware state")
    event = payload["event"]
    if not all(_number_is_present(event[field], briefing) for field in ("x", "y", "fall_duration_s")):
        raise ValueError("Gemini response omitted measured event facts")
    return briefing


async def generate_briefing(payload: dict, frame_b64: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    if not frame_b64:
        raise RuntimeError("frame_b64 is missing")

    body = json.dumps(
        {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": frame_b64}},
                    {"text": json.dumps(payload, separators=(",", ":"))},
                ],
            }],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 250,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        },
        separators=(",", ":"),
    ).encode("utf-8")

    def post() -> str:
        http_request = request.Request(
            GEMINI_ENDPOINT,
            data=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        with request.urlopen(http_request, timeout=GEMINI_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8")

    raw_response = await asyncio.wait_for(asyncio.to_thread(post), timeout=GEMINI_TIMEOUT_SECONDS)
    response = json.loads(raw_response)
    text = response["candidates"][0]["content"]["parts"][0]["text"]
    return _valid_briefing(text, payload)


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    # Hackathon shortcut: device posts and the deployed dashboard may come from different origins.
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
    if event.event_type == "FALL_DETECTED":
        briefing_payload = gemini_payload(event)
        try:
            payload["briefing"] = await generate_briefing(briefing_payload, event.frame_b64)
            payload["briefing_source"] = "gemini"
        except Exception:
            logger.exception("Gemini briefing failed; using fallback")
            payload["briefing"] = fallback_briefing(briefing_payload)
            payload["briefing_source"] = "fallback"
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
