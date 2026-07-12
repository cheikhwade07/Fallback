import argparse
import base64
from datetime import datetime, timezone
import json
import math
import time
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

import cv2
from ultralytics import YOLO

from capture import MODEL_PATH, fmt, open_camera, person_diagnostics, put_text
from fall_logic import (
    DOWN,
    FallStateMachine,
    FALL_CONFIRMED,
    RECOVERED,
    SubjectTracker,
    TrackCandidate,
    frame_verdict,
)


WINDOW_NAME = "Fallback Fall Detector"
DEFAULT_CONF = 0.15
DEFAULT_TRACK_CONF = 0.45
DEFAULT_SERVER = "http://localhost:8000"
NODE_ID = "node-01"


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat()


def annotated_jpeg(frame):
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("Could not encode annotated frame as JPEG.")
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def post_event(url, payload):
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=3.0) as response:
            response.read()
    except (HTTPError, URLError, TimeoutError) as error:
        print(f"POST failed: {error}", flush=True)


def marker(value, threshold, passes):
    if not math.isfinite(value):
        return "--"
    return "PASS" if passes else "FAIL"


def tracking_candidates(result, track_conf):
    if result.boxes is None or len(result.boxes) == 0:
        return []
    candidates = []
    for index, (confidence, bbox) in enumerate(zip(result.boxes.conf.tolist(), result.boxes.xyxy.tolist())):
        if confidence < track_conf:
            continue
        x1, y1, x2, y2 = bbox
        candidates.append(TrackCandidate(
            index=index,
            confidence=float(confidence),
            center=((x1 + x2) / 2.0, (y1 + y2) / 2.0),
            bbox=(x1, y1, x2, y2),
        ))
    return candidates


def draw_tracked_box(frame, tracked):
    if tracked is None:
        return
    x1, y1, x2, y2 = (round(value) for value in tracked.bbox)
    color = (255, 255, 0)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 4)
    put_text(frame, f"TRACKED {tracked.confidence:.2f}", (x1, max(24, y1 - 10)), .7, color, 2)


def draw_hud(frame, state, down_since, diagnostics, down_fraction, latency_ms,
             tracked_conf, n_candidates, n_persons):
    now = time.perf_counter()
    elapsed = 0.0 if down_since is None else max(0.0, now - down_since)
    torso = diagnostics.get("torso_angle", "")
    gap = diagnostics.get("sh_hip_gap_norm", "")
    try:
        torso_value = float(torso)
    except (TypeError, ValueError):
        torso_value = math.nan
    try:
        gap_value = float(gap)
    except (TypeError, ValueError):
        gap_value = math.nan
    lines = (
        (f"STATE: {state}   DOWN: {elapsed:.1f}s", 1.35, (0, 255, 255), 4),
        (f"torso_angle: {fmt(torso) if torso != '' else '--'} / >15.0 [{marker(torso_value, 15.0, torso_value > 15.0)}]", .75, (255, 255, 255), 2),
        (f"sh_hip_gap_norm: {fmt(gap, 3) if gap != '' else '--'} / <0.25 [{marker(gap_value, .25, gap_value < .25)}]", .75, (255, 255, 255), 2),
        (f"kp_ok: {diagnostics.get('kp_ok', 0)}   tracked conf: {'--' if tracked_conf is None else f'{tracked_conf:.2f}'}", .75, (255, 255, 255), 2),
        (f"candidates: {n_candidates}   n_persons raw: {n_persons}", .75, (255, 255, 255), 2),
        (f"window DOWN: {'--' if down_fraction is None else f'{down_fraction:.2f}'}   latency_ms: {latency_ms:.1f}", .75, (255, 255, 255), 2),
    )
    y = 48
    for text, scale, color, thickness in lines:
        put_text(frame, text, (12, y), scale, color, thickness)
        y += 42 if scale > 1 else 31
    put_text(frame, "UNKNOWN frames do not reset timer", (12, y + 8), .65, (0, 200, 255), 2)
    if state == FALL_CONFIRMED:
        put_text(frame, "LATCHED - press c to clear", (12, y + 40), .9, (0, 0, 255), 3)


def transition_timestamp(perf_counter_value):
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def main():
    parser = argparse.ArgumentParser(description="YOLO pose fall detector.")
    parser.add_argument("--conf", type=float, default=DEFAULT_CONF)
    parser.add_argument("--track-conf", type=float, default=DEFAULT_TRACK_CONF)
    parser.add_argument("--no-post", action="store_true", help="Do not POST events to the backend.")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="Backend server base URL.")
    args = parser.parse_args()

    cap = open_camera()
    model = YOLO(MODEL_PATH)
    machine = FallStateMachine()
    tracker = SubjectTracker()
    fall_posted = False
    last_down_since = None
    try:
        while True:
            frame_started = time.perf_counter()
            ok, frame = cap.read()
            if not ok or frame is None:
                print("ERROR: Webcam stopped returning frames.")
                break
            result = model(frame, conf=args.conf, verbose=False)[0]
            n_persons = 0 if result.boxes is None else len(result.boxes)
            candidates = tracking_candidates(result, args.track_conf)
            tracked = tracker.select(candidates, frame.shape[1], time.perf_counter())
            diagnostics = person_diagnostics(result[tracked.index]) if tracked is not None else {
                "torso_angle": "", "sh_hip_gap_norm": "", "kp_ok": 0, "conf": "",
            }
            verdict = frame_verdict(diagnostics, int(tracked is not None))
            decision_latency_ms = (time.perf_counter() - frame_started) * 1000.0
            transitions = machine.update(verdict, time.perf_counter())
            display = result.plot() if n_persons else frame.copy()
            draw_tracked_box(display, tracked)
            draw_hud(display, machine.state, machine.down_since, diagnostics,
                      machine.down_fraction, decision_latency_ms,
                      None if tracked is None else tracked.confidence,
                      len(candidates), n_persons)

            for transition in transitions:
                print(f"{transition_timestamp(transition.at)}: {transition.old_state} -> {transition.new_state}", flush=True)
                if transition.new_state == DOWN:
                    last_down_since = transition.at
                elif transition.new_state == FALL_CONFIRMED and not fall_posted:
                    fall_posted = True
                    fall_duration = transition.at - (last_down_since or transition.at)
                    payload = {
                        "node_id": NODE_ID,
                        "event_type": "FALL_DETECTED",
                        "x": 3.2,  # TODO: homography
                        "y": 1.4,  # TODO: homography
                        "fall_duration": fall_duration,
                        "latency_ms": decision_latency_ms,
                        "timestamp": utc_timestamp(),
                        "frame_b64": annotated_jpeg(display),
                    }
                    if not args.no_post:
                        post_event(f"{args.server.rstrip('/')}/api/event", payload)
            cv2.imshow(WINDOW_NAME, display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("c"):
                for transition in machine.clear(time.perf_counter()):
                    print(f"{transition_timestamp(transition.at)}: {transition.old_state} -> {transition.new_state}", flush=True)
                    if transition.new_state == RECOVERED:
                        payload = {
                            "node_id": NODE_ID,
                            "event_type": "RECOVERED",
                            "x": 3.2,  # TODO: homography
                            "y": 1.4,  # TODO: homography
                            "fall_duration": 0.0 if last_down_since is None else transition.at - last_down_since,
                            "latency_ms": decision_latency_ms,
                            "timestamp": utc_timestamp(),
                            "frame_b64": annotated_jpeg(display),
                        }
                        if not args.no_post:
                            post_event(f"{args.server.rstrip('/')}/api/event", payload)
                        fall_posted = False
                        last_down_since = None
            elif key == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
