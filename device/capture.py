import csv
import argparse
from datetime import datetime
import math
from collections import deque
from pathlib import Path
import statistics
import sys
import time

import cv2
from ultralytics import YOLO


WINDOW_NAME = "Fallback Pose Capture"
MODEL_PATH = "yolov8n-pose.pt"
LOG_DIR = Path(__file__).with_name("logs")
SUMMARY_PATH = Path(__file__).with_name("summary.txt")
KEYPOINT_CONF = 0.3
DEFAULT_CONF = 0.15
COUNTDOWN_SECONDS = 8.0
RECORD_SECONDS = 15.0
FPS_WINDOW = 30

LABELS = {
    ord("1"): "standing",
    ord("3"): "kneeling",
    ord("5"): "fallen",
}
UPRIGHT = ("standing", "kneeling")
FALLEN = ("fallen",)
LOG_COLUMNS = (
    "session_id", "t_rel", "label", "ms", "n_persons", "conf", "bbox_w", "bbox_h",
    "aspect", "sh_y", "hip_y", "sh_hip_gap", "sh_hip_gap_norm",
    "torso_angle", "ank_y", "kp_ok",
)


def open_camera():
    for index in (0, 1):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if cap.isOpened():
            print(f"Opened webcam index {index}.")
            return cap
        cap.release()
    print("ERROR: Could not open webcam index 0 or 1.")
    print("Check that the camera is connected, enabled, and not already in use.")
    sys.exit(1)


def person_diagnostics(result):
    values = {name: "" for name in LOG_COLUMNS[5:-1]}
    values["kp_ok"] = 0
    if result.boxes is None or len(result.boxes) == 0:
        return values

    boxes = result.boxes.xyxy
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    person_index = int(areas.argmax().item())
    values["conf"] = float(result.boxes.conf[person_index].item())
    x1, y1, x2, y2 = result.boxes.xyxy[person_index].tolist()
    bbox_w, bbox_h = x2 - x1, y2 - y1
    values["bbox_w"], values["bbox_h"] = bbox_w, bbox_h
    values["aspect"] = bbox_w / bbox_h if bbox_h > 0 else ""

    if result.keypoints is None or result.keypoints.data.shape[0] <= person_index:
        return values
    keypoints = result.keypoints.data[person_index]
    values["kp_ok"] = int((keypoints[:, 2] >= KEYPOINT_CONF).sum().item())

    def midpoint(first, second):
        pair = keypoints[[first, second]]
        if not bool((pair[:, 2] >= KEYPOINT_CONF).all().item()):
            return None
        return float(pair[:, 0].mean().item()), float(pair[:, 1].mean().item())

    shoulders = midpoint(5, 6)
    hips = midpoint(11, 12)
    ankles = midpoint(15, 16)
    if shoulders:
        values["sh_y"] = shoulders[1]
    if hips:
        values["hip_y"] = hips[1]
    if ankles:
        values["ank_y"] = ankles[1]
    if shoulders and hips:
        gap = abs(hips[1] - shoulders[1])
        values["sh_hip_gap"] = gap
        scale = max(bbox_w, bbox_h)
        values["sh_hip_gap_norm"] = gap / scale if scale > 0 else ""
        values["torso_angle"] = math.degrees(
            math.atan2(abs(hips[0] - shoulders[0]), abs(hips[1] - shoulders[1]))
        )
    return values


def fmt(value, digits=2):
    return "--" if value == "" else f"{value:.{digits}f}"


def put_text(frame, text, origin, scale=0.72, color=(255, 255, 255), thickness=2):
    x, y = origin
    cv2.putText(frame, text, (x + 2, y + 2), cv2.FONT_HERSHEY_SIMPLEX,
                scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                scale, color, thickness, cv2.LINE_AA)


def draw_overlay(frame, fps, elapsed_ms, n_persons, label, diagnostics,
                 countdown_left=None, recording_left=None):
    hip_yes = diagnostics["hip_y"] != ""
    ankle_yes = diagnostics["ank_y"] != ""
    lines = (
        f"conf: {fmt(diagnostics['conf'])}   kp_ok: {diagnostics['kp_ok']}   n_persons: {n_persons}",
        f"aspect: {fmt(diagnostics['aspect'])}   sh_hip_gap_norm: {fmt(diagnostics['sh_hip_gap_norm'], 3)}",
        f"HIP: {'yes' if hip_yes else 'no'}   ANK: {'yes' if ankle_yes else 'no'}   FPS: {fps:.1f}   ms: {elapsed_ms:.1f}",
    )
    put_text(frame, f"LABEL: {label.upper()}", (12, 48), 1.45, (0, 255, 255), 4)
    for index, line in enumerate(lines):
        put_text(frame, line, (12, 88 + index * 31))

    height, width = frame.shape[:2]
    if countdown_left is not None:
        number = str(max(1, math.ceil(countdown_left)))
        scale = max(3.0, min(width, height) / 125.0)
        size = cv2.getTextSize(number, cv2.FONT_HERSHEY_SIMPLEX, scale, 10)[0]
        put_text(frame, number, ((width - size[0]) // 2, (height + size[1]) // 2),
                 scale, (0, 255, 255), 10)
        put_text(frame, "GET READY", (max(12, width // 2 - 110), height - 35),
                 1.0, (0, 255, 255), 3)
    elif recording_left is not None:
        cv2.circle(frame, (25, 165), 10, (0, 0, 255), -1)
        put_text(frame, f"RECORDING  {recording_left:04.1f}s", (45, 173),
                 0.9, (0, 0, 255), 3)
    else:
        put_text(frame, "IDLE - press SPACE to capture", (12, 173), 0.8, (0, 255, 0), 2)


def create_session_log():
    LOG_DIR.mkdir(exist_ok=True)
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = LOG_DIR / f"pose_{session_id}.csv"
    suffix = 1
    while path.exists():
        path = LOG_DIR / f"pose_{session_id}_{suffix}.csv"
        suffix += 1
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_COLUMNS)
        writer.writeheader()
    return session_id, path


def append_row(log_path, row):
    with log_path.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=LOG_COLUMNS).writerow(row)


def percentile(values, percent):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100.0
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def read_rows(log_path):
    if not log_path.exists() or log_path.stat().st_size == 0:
        return []
    with log_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def numeric(rows, field):
    output = []
    for row in rows:
        try:
            if row.get(field, "") != "":
                output.append(float(row[field]))
        except (TypeError, ValueError):
            pass
    return output


def build_summary(log_path):
    rows = read_rows(log_path)
    header = "label             | n_frames | hips detected | median aspect | median sh_hip_gap_norm | median torso_angle"
    lines = [header, "-" * len(header)]
    for label in ("unlabeled", *LABELS.values()):
        group = [row for row in rows if row.get("label") == label]
        hips = sum(row.get("hip_y", "") != "" for row in group)
        hip_percent = 100.0 * hips / len(group) if group else 0.0
        medians = []
        for field in ("aspect", "sh_hip_gap_norm", "torso_angle"):
            values = numeric(group, field)
            medians.append(f"{statistics.median(values):.3f}" if values else "--")
        lines.append(
            f"{label:<17} | {len(group):>8} | {hip_percent:>12.1f}% | "
            f"{medians[0]:>13} | {medians[1]:>22} | {medians[2]:>18}"
        )

    lines.extend(["", "separation check (upright p90 vs fallen p10)"])
    upright_rows = [row for row in rows if row.get("label") in UPRIGHT]
    fallen_rows = [row for row in rows if row.get("label") in FALLEN]
    for field in ("aspect", "sh_hip_gap_norm", "torso_angle"):
        up = percentile(numeric(upright_rows, field), 90)
        down = percentile(numeric(fallen_rows, field), 10)
        lines.append(f"{field:<20} | upright p90: {fmt(up, 3) if up is not None else '--':>8} | fallen p10: {fmt(down, 3) if down is not None else '--':>8}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Capture labeled pose diagnostics.")
    parser.add_argument("--conf", type=float, default=DEFAULT_CONF,
                        help=f"YOLO detection confidence threshold (default: {DEFAULT_CONF})")
    args = parser.parse_args()
    session_id, log_path = create_session_log()
    print(f"Session {session_id}; logging to {log_path}.")
    cap = open_camera()
    print(f"Loading {MODEL_PATH}.")
    model = YOLO(MODEL_PATH)
    selected_label = "unlabeled"
    phase = "idle"
    phase_started = 0.0
    elapsed_times = deque(maxlen=FPS_WINDOW)

    try:
        while True:
            frame_started = time.perf_counter()
            ok, frame = cap.read()
            if not ok or frame is None:
                print("ERROR: Webcam stopped returning frames.")
                break

            result = model(frame, conf=args.conf, verbose=False)[0]
            n_persons = 0 if result.boxes is None else len(result.boxes)
            diagnostics = person_diagnostics(result)
            display = result.plot() if n_persons else frame.copy()
            inference_elapsed = time.perf_counter() - frame_started
            mean_elapsed = (sum(elapsed_times) + inference_elapsed) / (len(elapsed_times) + 1)
            fps = 1.0 / mean_elapsed if mean_elapsed else 0.0
            now = time.perf_counter()

            countdown_left = recording_left = None
            if phase == "countdown":
                countdown_left = COUNTDOWN_SECONDS - (now - phase_started)
                if countdown_left <= 0:
                    phase, phase_started = "recording", now
                    countdown_left, recording_left = None, RECORD_SECONDS
                    print(f"Recording {selected_label}...")
            elif phase == "recording":
                recording_left = RECORD_SECONDS - (now - phase_started)
                if recording_left <= 0:
                    phase, recording_left = "idle", None
                    print(f"Finished recording {selected_label}.")

            draw_overlay(display, fps, inference_elapsed * 1000.0, n_persons,
                         selected_label, diagnostics, countdown_left, recording_left)
            cv2.imshow(WINDOW_NAME, display)
            elapsed_times.append(time.perf_counter() - frame_started)
            key = cv2.waitKey(1) & 0xFF
            if key in LABELS:
                selected_label = LABELS[key]
                print(f"Selected label: {selected_label}")
            elif key == ord(" ") and phase == "idle":
                phase, phase_started = "countdown", time.perf_counter()
                print(f"Countdown started for {selected_label}.")
            elif key == ord("q"):
                break

            if phase == "recording":
                append_row(log_path, {
                    "session_id": session_id,
                    "t_rel": f"{now - phase_started:.3f}",
                    "label": selected_label,
                    "ms": f"{inference_elapsed * 1000.0:.1f}",
                    "n_persons": n_persons,
                    **{key: (f"{value:.6f}" if isinstance(value, float) else value)
                       for key, value in diagnostics.items()},
                })
    finally:
        cap.release()
        cv2.destroyAllWindows()
        summary = build_summary(log_path)
        print("\n" + summary)
        SUMMARY_PATH.write_text(summary + "\n", encoding="utf-8")
        print(f"\nSummary saved to {SUMMARY_PATH}.")


if __name__ == "__main__":
    main()
