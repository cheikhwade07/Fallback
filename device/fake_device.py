import argparse
import base64
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

import cv2
import numpy as np


def load_frame() -> str:
    frame_path = Path(__file__).with_name("test_frame.jpg")
    frame = cv2.imread(str(frame_path)) if frame_path.exists() else None
    if frame is None:
        frame = np.full((360, 640, 3), (35, 35, 35), dtype=np.uint8)
        cv2.putText(
            frame,
            "FAKE FRAME",
            (150, 200),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (255, 255, 255),
            3,
            cv2.LINE_AA,
        )

    height, width = frame.shape[:2]
    if width > 640:
        scale = 640 / width
        frame = cv2.resize(
            frame,
            (640, round(height * scale)),
            interpolation=cv2.INTER_AREA,
        )

    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if not ok:
        raise RuntimeError("Could not encode fake frame as JPEG")
    return base64.b64encode(jpeg.tobytes()).decode("ascii")


def post_event(
    base_url: str,
    event_type: str,
    fall_duration: float,
    frame_b64: str,
    x: float | None = None,
    y: float | None = None,
) -> None:
    payload = {
        "node_id": "node-01",
        "event_type": event_type,
        "x": round(random.uniform(0, 10) if x is None else x, 2),
        "y": round(random.uniform(0, 10) if y is None else y, 2),
        "fall_duration": round(fall_duration, 1),
        "latency_ms": round(random.uniform(60, 120), 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "frame_b64": frame_b64,
    }
    body = json.dumps(payload).encode("utf-8")
    post = request.Request(
        f"{base_url.rstrip('/')}/api/event",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    result = (
        f"{event_type}: x={payload['x']} y={payload['y']} "
        f"fall_duration={payload['fall_duration']}"
    )
    try:
        with request.urlopen(post) as response:
            print(f"{result} HTTP {response.status}", flush=True)
    except error.HTTPError as exc:
        print(f"{result} HTTP {exc.code}", flush=True)
    except error.URLError as exc:
        print(f"{result} POST failed: {exc.reason}", flush=True)


def run_scenario(
    scenario: str,
    url: str,
    frame_b64: str,
    x: float | None = None,
    y: float | None = None,
) -> None:
    if scenario == "once":
        post_event(url, "FALL_DETECTED", 0, frame_b64, x, y)
        return

    if scenario == "heartbeat":
        while True:
            post_event(url, "HEARTBEAT", 0, frame_b64, x, y)
            time.sleep(2)

    fall_x = round(random.uniform(0, 10) if x is None else x, 2)
    fall_y = round(random.uniform(0, 10) if y is None else y, 2)
    started = time.monotonic()
    post_event(url, "FALL_DETECTED", 0, frame_b64, fall_x, fall_y)
    for target_second in range(2, 20, 2):
        time.sleep(max(0, started + target_second - time.monotonic()))
        elapsed = time.monotonic() - started
        post_event(url, "HEARTBEAT", elapsed, frame_b64, fall_x, fall_y)
    time.sleep(max(0, started + 20 - time.monotonic()))
    elapsed = time.monotonic() - started
    post_event(url, "RECOVERED", elapsed, frame_b64, fall_x, fall_y)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send fake events to the Fallback backend")
    parser.add_argument("--scenario", choices=("fall", "heartbeat", "once"), default="fall")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--x", type=float)
    parser.add_argument("--y", type=float)
    args = parser.parse_args()
    run_scenario(args.scenario, args.url, load_frame(), args.x, args.y)


if __name__ == "__main__":
    main()
