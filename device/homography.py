"""Interactive floor-marker calibration for the fallback device."""

from datetime import datetime, timezone
import json
from pathlib import Path
import time

import cv2
import numpy as np

from capture import open_camera


# Calibration config: edit these only if the marker layout changes.
WORLD_POINTS = {
    "A": (0.00, 0.00),
    "B": (2.00, 0.00),  # entrance / door corner
    "C": (2.00, 2.00),
    "D": (0.00, 2.00),
}
MARKER_ORDER = ("A", "B", "C", "D")
OUTPUT_PATH = Path(__file__).with_name("homography.json")
WINDOW_NAME = "Fallback Homography Calibration"


def draw_points(frame, points):
    display = frame.copy()
    for label, point in points:
        x, y = (round(value) for value in point)
        cv2.circle(display, (x, y), 9, (0, 0, 255), -1)
        cv2.putText(display, label, (x + 14, y - 14), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, (0, 255, 255), 2, cv2.LINE_AA)
    return display


def main():
    cap = open_camera()
    # Give autofocus, auto-exposure, and auto-white-balance time to settle.
    time.sleep(1.0)
    ok, frame = False, None
    for _ in range(5):
        ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise RuntimeError("Could not capture a calibration frame.")
    # The calibration frame is static, so denoise only this preview to make
    # marker edges easier to see; pixel coordinates and aspect ratio are kept.
    frame = cv2.fastNlMeansDenoisingColored(frame, None, 3, 3, 7)

    points = []

    def on_mouse(event, x, y, _flags, _param):
        if event != cv2.EVENT_LBUTTONDOWN or len(points) >= len(MARKER_ORDER):
            return
        label = MARKER_ORDER[len(points)]
        points.append((label, (float(x), float(y))))
        print(f"Captured {label} at image ({x}, {y}).", flush=True)
        if len(points) < len(MARKER_ORDER):
            print(f"Click marker {MARKER_ORDER[len(points)]}.", flush=True)
        else:
            print("All four markers captured. Press any key to compute.", flush=True)

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, min(frame.shape[1], 1600), min(frame.shape[0], 900))
    cv2.setMouseCallback(WINDOW_NAME, on_mouse)
    print("Frame frozen. Click marker A.", flush=True)
    print("Controls: u = undo last click, r = restart, q = quit.", flush=True)
    try:
        while True:
            cv2.imshow(WINDOW_NAME, draw_points(frame, points))
            key = cv2.waitKey(20) & 0xFF
            if key == ord("q"):
                return
            if key == ord("u") and points:
                removed, _ = points.pop()
                print(f"Undid marker {removed}. Click marker {removed}.", flush=True)
            elif key == ord("r"):
                points.clear()
                print("Restarted. Click marker A.", flush=True)
            elif len(points) == len(MARKER_ORDER) and key != 255:
                break
    finally:
        cv2.destroyAllWindows()

    image_pts = np.float32([point for _, point in points])
    world_pts = np.float32([WORLD_POINTS[label] for label, _ in points])
    matrix = cv2.getPerspectiveTransform(image_pts, world_pts)
    projected = cv2.perspectiveTransform(image_pts.reshape(-1, 1, 2), matrix).reshape(-1, 2)

    print("Verification (projected world coordinate vs expected):", flush=True)
    bad = False
    for (label, _), actual, expected in zip(points, projected, world_pts):
        error_cm = float(np.linalg.norm(actual - expected) * 100.0)
        print(
            f"{label}: ({actual[0]:.3f}, {actual[1]:.3f}) m vs "
            f"({expected[0]:.3f}, {expected[1]:.3f}) m; error {error_cm:.3f} cm",
            flush=True,
        )
        bad |= error_cm > 5.0
    if bad:
        print("!!! WARNING: CALIBRATION IS BAD (> 5 cm). REDO CALIBRATION. !!!", flush=True)

    payload = {
        "matrix": matrix.tolist(),
        "image_points": [list(point) for _, point in points],
        "world_points": [list(WORLD_POINTS[label]) for label, _ in points],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Saved calibration to {OUTPUT_PATH}.", flush=True)


if __name__ == "__main__":
    main()
