import argparse
from collections import deque
import csv
from pathlib import Path
import sys
import time

import cv2
from ultralytics import YOLO


WINDOW_NAME = "Fallback Pose View"
MODEL_PATH = "yolov8n-pose.pt"
FPS_WINDOW = 30
LOG_PATH = Path(__file__).with_name("pose_log.csv")
LOG_COLUMNS = (
    "t_rel",
    "label",
    "ms",
    "n_persons",
    "conf",
    "bbox_w",
    "bbox_h",
    "aspect",
    "sh_y",
    "hip_y",
    "sh_hip_gap",
    "ank_y",
    "kp_ok",
)


def parse_args():
    parser = argparse.ArgumentParser(description="View YOLO pose detections from a webcam.")
    parser.add_argument("--log", action="store_true", help="Append per-frame diagnostics to pose_log.csv.")
    parser.add_argument("--label", default="none", help="Label stored with each logged frame.")
    parser.add_argument("--clear", action="store_true", help="Delete pose_log.csv before starting.")
    return parser.parse_args()


def open_camera():
    for index in (0, 1):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            continue

        print(f"Opened webcam index {index}.")
        return cap

    print("ERROR: Could not read a frame from webcam index 0 or 1.")
    print("Check that the camera is connected, enabled, and not already in use.")
    sys.exit(1)


def count_persons(result):
    if result.boxes is None:
        return 0
    return len(result.boxes)


def person_diagnostics(result):
    empty = {
        "conf": "",
        "bbox_w": "",
        "bbox_h": "",
        "aspect": "",
        "sh_y": "",
        "hip_y": "",
        "sh_hip_gap": "",
        "ank_y": "",
        "kp_ok": 0,
    }
    if result.boxes is None or len(result.boxes) == 0:
        return empty

    confidences = result.boxes.conf
    person_index = int(confidences.argmax().item())
    confidence = float(confidences[person_index].item())
    x1, y1, x2, y2 = result.boxes.xyxy[person_index].tolist()
    bbox_w = int(round(x2 - x1))
    bbox_h = int(round(y2 - y1))
    aspect = bbox_w / bbox_h if bbox_h else None

    values = {
        **empty,
        "conf": f"{confidence:.2f}",
        "bbox_w": bbox_w,
        "bbox_h": bbox_h,
        "aspect": f"{aspect:.2f}" if aspect is not None else "",
    }
    if result.keypoints is None or result.keypoints.data.shape[0] <= person_index:
        return values

    keypoints = result.keypoints.data[person_index]
    values["kp_ok"] = int((keypoints[:, 2] >= 0.3).sum().item())

    def mean_y(first, second):
        pair = keypoints[[first, second]]
        if bool((pair[:, 2] >= 0.3).all().item()):
            return int(round(float(pair[:, 1].mean().item())))
        return ""

    values["sh_y"] = mean_y(5, 6)
    values["hip_y"] = mean_y(11, 12)
    values["ank_y"] = mean_y(15, 16)
    if values["sh_y"] != "" and values["hip_y"] != "":
        values["sh_hip_gap"] = abs(values["hip_y"] - values["sh_y"])
    return values


def draw_overlay(frame, fps, elapsed_ms, persons, label, diagnostics):
    aspect = diagnostics["aspect"] or "--"
    gap = diagnostics["sh_hip_gap"] if diagnostics["sh_hip_gap"] != "" else "--"
    lines = (
        f"FPS: {fps:.1f}  {elapsed_ms:.1f} ms",
        f"Persons: {persons}",
        f"Label: {label}  aspect: {aspect}  sh_hip_gap: {gap}",
    )
    x, y = 12, 28

    for line in lines:
        cv2.putText(
            frame,
            line,
            (x + 1, y + 1),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 0),
            3,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            line,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        y += 32


def main():
    args = parse_args()
    if args.clear and LOG_PATH.exists():
        LOG_PATH.unlink()
        print(f"Cleared {LOG_PATH}.")

    cap = open_camera()

    print(f"Loading {MODEL_PATH}. First run may download the model weights; please wait.")
    model = YOLO(MODEL_PATH)

    elapsed_times = deque(maxlen=FPS_WINDOW)
    start_time = time.perf_counter()
    log_file = None
    log_writer = None
    if args.log:
        write_header = not LOG_PATH.exists()
        log_file = LOG_PATH.open("a", newline="", encoding="utf-8")
        log_writer = csv.DictWriter(log_file, fieldnames=LOG_COLUMNS)
        if write_header:
            log_writer.writeheader()

    try:
        while True:
            t0 = time.perf_counter()

            ok, frame = cap.read()
            if not ok or frame is None:
                print("ERROR: Webcam stopped returning frames.")
                break

            results = model(frame, verbose=False)
            result = results[0]
            persons = count_persons(result)
            diagnostics = person_diagnostics(result)

            if persons > 0:
                display = result.plot()
            else:
                display = frame.copy()

            elapsed_before_overlay = time.perf_counter() - t0
            mean_elapsed = (
                (sum(elapsed_times) + elapsed_before_overlay) / (len(elapsed_times) + 1)
            )
            fps = 1.0 / mean_elapsed if mean_elapsed > 0 else 0.0

            draw_overlay(
                display,
                fps,
                elapsed_before_overlay * 1000.0,
                persons,
                args.label,
                diagnostics,
            )
            elapsed = time.perf_counter() - t0
            elapsed_times.append(elapsed)

            if log_writer is not None:
                log_writer.writerow(
                    {
                        "t_rel": f"{time.perf_counter() - start_time:.2f}",
                        "label": args.label,
                        "ms": f"{elapsed * 1000.0:.1f}",
                        "n_persons": persons,
                        **diagnostics,
                    }
                )
                log_file.flush()
            cv2.imshow(WINDOW_NAME, display)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        if log_file is not None:
            log_file.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
