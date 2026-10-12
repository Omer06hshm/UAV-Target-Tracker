"""Live RED/BLUE square-target tracker for OBS Virtual Camera.

Implements GitHub issue #1. Independent lock state per color, persistence
before lock, continuity-over-score while locked, brief hold on miss, and
smooth box resize. Q/Esc exit. M toggles mask windows.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import cv2
import numpy as np

CAMERA_INDEX = 2
PROCESS_WIDTH = 640
PROCESS_HEIGHT = 360
WINDOW_NAME = "UAV Target Tracker"

# HSV ranges from issue #1 (OpenCV hue is 0-180).
BLUE_HSV_LOW = (90, 60, 40)
BLUE_HSV_HIGH = (135, 255, 255)
RED_LOW_HSV_LOW = (0, 70, 50)
RED_LOW_HSV_HIGH = (12, 255, 255)
RED_HIGH_HSV_LOW = (168, 70, 50)
RED_HIGH_HSV_HIGH = (180, 255, 255)

MORPH_KERNEL = 3
MIN_AREA = 80
MAX_AREA_FRAC = 0.35
ASPECT_MIN = 0.55
ASPECT_MAX = 1.80
FILL_MIN = 0.45

LOCK_CONFIRM_FRAMES = 5
MISS_GRACE_FRAMES = 12
REACQUIRE_CONFIRM_FRAMES = 4
SMOOTH_ALPHA = 0.35
GATE_SCALE = 2.4
JUMP_SCORE_MARGIN = 1.35
PREDICT_DECAY = 0.85


@dataclass
class Candidate:
    cx: float
    cy: float
    width: float
    height: float
    area: float
    fill: float
    color_score: float
    box: np.ndarray


@dataclass
class ColorTracker:
    name: str
    color_bgr: tuple[int, int, int]
    locked: bool = False
    confirming: int = 0
    missed: int = 0
    reacquire: int = 0
    cx: float = 0.0
    cy: float = 0.0
    width: float = 0.0
    height: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    last_box: np.ndarray | None = field(default=None, repr=False)

    def predicted_center(self) -> tuple[float, float]:
        return (self.cx + self.vx, self.cy + self.vy)

    def healthy(self) -> bool:
        return self.locked and self.missed < MISS_GRACE_FRAMES // 2


def _mask_blue(hsv: np.ndarray) -> np.ndarray:
    return cv2.inRange(hsv, np.array(BLUE_HSV_LOW), np.array(BLUE_HSV_HIGH))


def _mask_red(hsv: np.ndarray) -> np.ndarray:
    low = cv2.inRange(hsv, np.array(RED_LOW_HSV_LOW), np.array(RED_LOW_HSV_HIGH))
    high = cv2.inRange(hsv, np.array(RED_HIGH_HSV_LOW), np.array(RED_HIGH_HSV_HIGH))
    return cv2.bitwise_or(low, high)


def _clean_mask(mask: np.ndarray) -> np.ndarray:
    kernel = np.ones((MORPH_KERNEL, MORPH_KERNEL), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    return mask


def _square_candidates(mask: np.ndarray, frame_area: int) -> list[Candidate]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    found: list[Candidate] = []
    max_area = frame_area * MAX_AREA_FRAC
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < MIN_AREA or area > max_area:
            continue
        rect = cv2.minAreaRect(contour)
        (cx, cy), (rw, rh), _ = rect
        if rw < 1 or rh < 1:
            continue
        ratio = rw / rh
        if not (ASPECT_MIN <= ratio <= ASPECT_MAX):
            continue
        fill = float(area / (rw * rh))
        if fill < FILL_MIN:
            continue
        color_score = fill * np.sqrt(area)
        box = np.intp(cv2.boxPoints(rect))
        found.append(
            Candidate(
                cx=float(cx),
                cy=float(cy),
                width=float(rw),
                height=float(rh),
                area=float(area),
                fill=fill,
                color_score=float(color_score),
                box=box,
            )
        )
    found.sort(key=lambda item: item.color_score, reverse=True)
    return found[:8]


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def _gate_radius(tracker: ColorTracker) -> float:
    size = max(tracker.width, tracker.height, 12.0)
    return GATE_SCALE * size


def _choose_candidate(tracker: ColorTracker, candidates: list[Candidate]) -> Candidate | None:
    if not candidates:
        return None

    best_color = candidates[0]
    if not tracker.locked and tracker.confirming == 0:
        return best_color

    px, py = tracker.predicted_center()
    gate = _gate_radius(tracker)
    nearby: list[tuple[float, Candidate]] = []
    for cand in candidates:
        dist = _distance((cand.cx, cand.cy), (px, py))
        if dist <= gate:
            nearby.append((dist, cand))

    if nearby:
        nearby.sort(key=lambda item: item[0] + (0.15 * (best_color.color_score / max(item[1].color_score, 1.0))))
        return nearby[0][1]

    if tracker.healthy():
        return None

    if tracker.locked:
        return None
    return best_color


def _apply_measurement(tracker: ColorTracker, cand: Candidate) -> None:
    if tracker.width <= 0:
        tracker.cx, tracker.cy = cand.cx, cand.cy
        tracker.width, tracker.height = cand.width, cand.height
        tracker.vx = 0.0
        tracker.vy = 0.0
    else:
        nx = SMOOTH_ALPHA * cand.cx + (1.0 - SMOOTH_ALPHA) * tracker.cx
        ny = SMOOTH_ALPHA * cand.cy + (1.0 - SMOOTH_ALPHA) * tracker.cy
        tracker.vx = PREDICT_DECAY * (nx - tracker.cx)
        tracker.vy = PREDICT_DECAY * (ny - tracker.cy)
        tracker.cx, tracker.cy = nx, ny
        tracker.width = SMOOTH_ALPHA * cand.width + (1.0 - SMOOTH_ALPHA) * tracker.width
        tracker.height = SMOOTH_ALPHA * cand.height + (1.0 - SMOOTH_ALPHA) * tracker.height
    tracker.last_box = cand.box


def _coast(tracker: ColorTracker) -> None:
    tracker.cx += tracker.vx
    tracker.cy += tracker.vy
    tracker.vx *= PREDICT_DECAY
    tracker.vy *= PREDICT_DECAY


def _reset(tracker: ColorTracker) -> None:
    tracker.locked = False
    tracker.confirming = 0
    tracker.missed = 0
    tracker.reacquire = 0
    tracker.cx = tracker.cy = 0.0
    tracker.width = tracker.height = 0.0
    tracker.vx = tracker.vy = 0.0
    tracker.last_box = None


def update_tracker(tracker: ColorTracker, candidates: list[Candidate]) -> None:
    chosen = _choose_candidate(tracker, candidates)
    if chosen is None:
        tracker.missed += 1
        tracker.confirming = 0
        if tracker.locked:
            _coast(tracker)
            if tracker.missed >= MISS_GRACE_FRAMES:
                tracker.locked = False
                tracker.reacquire = 1
                tracker.confirming = 0
        else:
            if tracker.missed > 2:
                _reset(tracker)
        return

    if tracker.locked:
        pred = tracker.predicted_center()
        dist = _distance((chosen.cx, chosen.cy), pred)
        if dist > _gate_radius(tracker) * JUMP_SCORE_MARGIN and tracker.healthy():
            tracker.missed += 1
            _coast(tracker)
            return
        _apply_measurement(tracker, chosen)
        tracker.missed = 0
        return

    if tracker.width <= 0:
        _apply_measurement(tracker, chosen)
        tracker.confirming = 1
        tracker.missed = 0
        return

    pred = tracker.predicted_center()
    dist = _distance((chosen.cx, chosen.cy), pred)
    same_object = dist <= _gate_radius(tracker)
    _apply_measurement(tracker, chosen)
    tracker.missed = 0
    if same_object:
        tracker.confirming += 1
        needed = REACQUIRE_CONFIRM_FRAMES if tracker.reacquire else LOCK_CONFIRM_FRAMES
        if tracker.confirming >= needed:
            tracker.locked = True
            tracker.reacquire = 0
    else:
        tracker.confirming = 1
        tracker.locked = False


def _draw_tracker(
    frame: np.ndarray,
    tracker: ColorTracker,
    center: tuple[int, int],
) -> None:
    if tracker.width <= 0 and not tracker.locked:
        return
    half_w = tracker.width / 2.0
    half_h = tracker.height / 2.0
    x1 = int(tracker.cx - half_w)
    y1 = int(tracker.cy - half_h)
    x2 = int(tracker.cx + half_w)
    y2 = int(tracker.cy + half_h)
    thickness = 2 if tracker.locked else 1
    cv2.rectangle(frame, (x1, y1), (x2, y2), tracker.color_bgr, thickness)
    err_x = tracker.cx - center[0]
    err_y = tracker.cy - center[1]
    state = "LOCK" if tracker.locked else ("HOLD" if tracker.missed else "ACQ")
    label = f"{tracker.name} {state}  errX={err_x:+.0f} errY={err_y:+.0f}"
    cv2.putText(
        frame,
        label,
        (x1, max(18, y1 - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        tracker.color_bgr,
        1,
        cv2.LINE_AA,
    )
    cv2.circle(frame, (int(tracker.cx), int(tracker.cy)), 3, tracker.color_bgr, -1)


def _open_camera(index: int) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, PROCESS_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, PROCESS_HEIGHT)
    return cap


def main() -> int:
    red = ColorTracker("RED", (0, 0, 255))
    blue = ColorTracker("BLUE", (255, 80, 0))
    show_masks = False

    cap = _open_camera(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"Could not open camera index {CAMERA_INDEX}. Start OBS Virtual Camera and retry.")
        return 1

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    prev = time.perf_counter()
    fps = 0.0
    print(f"Opened camera {CAMERA_INDEX}. Q or Esc to quit. M toggles masks.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("Camera frame grab failed.")
                break

            if frame.shape[1] != PROCESS_WIDTH or frame.shape[0] != PROCESS_HEIGHT:
                frame = cv2.resize(frame, (PROCESS_WIDTH, PROCESS_HEIGHT), interpolation=cv2.INTER_LINEAR)

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            red_mask = _clean_mask(_mask_red(hsv))
            blue_mask = _clean_mask(_mask_blue(hsv))
            frame_area = PROCESS_WIDTH * PROCESS_HEIGHT
            red_cands = _square_candidates(red_mask, frame_area)
            blue_cands = _square_candidates(blue_mask, frame_area)

            update_tracker(red, red_cands)
            update_tracker(blue, blue_cands)

            now = time.perf_counter()
            dt = now - prev
            prev = now
            if dt > 0:
                inst = 1.0 / dt
                fps = inst if fps == 0.0 else (0.85 * fps + 0.15 * inst)

            cx, cy = PROCESS_WIDTH // 2, PROCESS_HEIGHT // 2
            cv2.drawMarker(frame, (cx, cy), (0, 255, 255), cv2.MARKER_CROSS, 12, 1)
            _draw_tracker(frame, red, (cx, cy))
            _draw_tracker(frame, blue, (cx, cy))
            cv2.putText(
                frame,
                f"FPS {fps:5.1f}  cam {CAMERA_INDEX}  {PROCESS_WIDTH}x{PROCESS_HEIGHT}",
                (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

            cv2.imshow(WINDOW_NAME, frame)
            if show_masks:
                cv2.imshow("RED mask", red_mask)
                cv2.imshow("BLUE mask", blue_mask)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break
            if key in (ord("m"), ord("M")):
                show_masks = not show_masks
                if not show_masks:
                    cv2.destroyWindow("RED mask")
                    cv2.destroyWindow("BLUE mask")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print(f"Exit. Last smoothed FPS={fps:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
