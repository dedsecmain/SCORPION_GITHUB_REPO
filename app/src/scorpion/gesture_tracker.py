from __future__ import annotations

import math
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from urllib import request

from .build_mode import BuildGesture, BuildGestureEvent


HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)


def ensure_hand_model(
    path: str | Path | None = None,
    *,
    download_fn=None,
) -> Path:
    target = Path(path) if path is not None else (
        Path.home() / ".scorpion" / "models" / "hand_landmarker.task"
    )
    if target.is_file() and target.stat().st_size > 1_000_000:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".task.tmp")
    downloader = download_fn or request.urlretrieve
    try:
        downloader(HAND_MODEL_URL, str(tmp))
        if not tmp.is_file() or tmp.stat().st_size <= 1_000_000:
            raise GestureTrackingUnavailable("Hand-Landmarker-Modell ist unvollständig.")
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return target


def _distance(a, b) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _palm_angle(hand, mirror_x: bool) -> float | None:
    """Palm axis from index and pinky knuckles, unavailable if landmarks overlap."""
    if _distance(hand[5], hand[17]) < 0.045:
        return None
    angle = math.degrees(
        math.atan2(
            float(hand[17][1]) - float(hand[5][1]),
            float(hand[17][0]) - float(hand[5][0]),
        )
    )
    return -angle if mirror_x else angle


class GestureInterpreter:
    """Turns normalized hand landmarks into stable Build Mode events.

    MK74.0.2 adds hysteresis, short dropout tolerance, EMA smoothing and
    transform spike guards so noisy webcam tracking cannot constantly grab,
    release or fling virtual objects.
    """

    def __init__(
        self,
        *,
        pinch_threshold: float = 0.065,
        pinch_release_threshold: float = 0.085,
        middle_pinch_threshold: float = 0.055,
        middle_release_threshold: float = 0.075,
        rotation_gain: float = 260.0,
        mirror_x: bool = True,
        smoothing: float = 0.35,
        dropout_grace_frames: int = 2,
        max_rotation_step: float = 12.0,
        max_scale_step: float = 1.12,
        scale_deadzone: float = 0.03,
    ):
        self.pinch_threshold = float(pinch_threshold)
        self.pinch_release_threshold = max(
            self.pinch_threshold,
            float(pinch_release_threshold),
        )
        self.middle_pinch_threshold = float(middle_pinch_threshold)
        self.middle_release_threshold = max(
            self.middle_pinch_threshold,
            float(middle_release_threshold),
        )
        self.rotation_gain = float(rotation_gain)
        self.mirror_x = bool(mirror_x)
        self.smoothing = max(0.05, min(1.0, float(smoothing)))
        self.dropout_grace_frames = max(0, int(dropout_grace_frames))
        self.max_rotation_step = max(1.0, float(max_rotation_step))
        self.max_scale_step = max(1.001, float(max_scale_step))
        self.scale_deadzone = max(0.0, float(scale_deadzone))

        self._single_pinched = False
        self._pinch_states = [False, False]
        self._middle_pinched = False
        self._last_middle_x: float | None = None
        self._last_palm_angle: float | None = None
        self._two_hand_baseline: float | None = None
        self._missing_frames = 0
        self._smoothed: dict[tuple[int, int], tuple[float, float]] = {}

    @staticmethod
    def _valid(hand) -> bool:
        return isinstance(hand, (list, tuple)) and len(hand) >= 21

    def _workspace_point(self, point) -> tuple[float, float]:
        x, y = float(point[0]), float(point[1])
        return (1.0 - x if self.mirror_x else x), y

    def _smooth_workspace_point(
        self,
        hand_index: int,
        landmark_index: int,
        point,
    ) -> tuple[float, float]:
        current = self._workspace_point(point)
        key = (int(hand_index), int(landmark_index))
        previous = self._smoothed.get(key)
        if previous is None:
            smoothed = current
        else:
            alpha = self.smoothing
            smoothed = (
                previous[0] + alpha * (current[0] - previous[0]),
                previous[1] + alpha * (current[1] - previous[1]),
            )
        self._smoothed[key] = smoothed
        return smoothed

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, float(value)))

    def _index_pinch_state(self, hand_index: int, distance: float) -> bool:
        previous = self._pinch_states[hand_index]
        if previous:
            active = distance <= self.pinch_release_threshold
        else:
            active = distance <= self.pinch_threshold
        self._pinch_states[hand_index] = active
        return active

    def _middle_pinch_state(self, distance: float) -> bool:
        if self._middle_pinched:
            active = distance <= self.middle_release_threshold
        else:
            active = distance <= self.middle_pinch_threshold
        self._middle_pinched = active
        return active

    def _release_single_pinch(self, events: list[BuildGestureEvent]) -> None:
        if self._single_pinched:
            events.append(BuildGestureEvent(BuildGesture.PINCH_END))
            self._single_pinched = False

    def _hard_reset_tracking(self, events: list[BuildGestureEvent]) -> None:
        self._release_single_pinch(events)
        self._pinch_states = [False, False]
        self._middle_pinched = False
        self._last_middle_x = None
        self._last_palm_angle = None
        self._two_hand_baseline = None
        self._smoothed.clear()

    def update(self, hands) -> list[BuildGestureEvent]:
        valid = [hand for hand in hands if self._valid(hand)][:2]
        events: list[BuildGestureEvent] = []

        if not valid:
            self._missing_frames += 1
            if self._missing_frames <= self.dropout_grace_frames:
                return events
            self._hard_reset_tracking(events)
            return events

        self._missing_frames = 0

        # MediaPipe may swap hand order frame-to-frame. Stable left-to-right
        # ordering prevents the smoothing state from jumping between hands.
        valid.sort(key=lambda hand: float(hand[8][0]))

        index_pinches: list[bool] = []
        for index, hand in enumerate(valid):
            distance = _distance(hand[4], hand[8])
            index_pinches.append(self._index_pinch_state(index, distance))
        for index in range(len(valid), 2):
            self._pinch_states[index] = False

        if len(valid) >= 2 and all(index_pinches[:2]):
            p1 = self._smooth_workspace_point(0, 8, valid[0][8])
            p2 = self._smooth_workspace_point(1, 8, valid[1][8])
            span = max(0.02, _distance(p1, p2))
            if self._two_hand_baseline is None:
                self._two_hand_baseline = span
                if not self._single_pinched:
                    x = (p1[0] + p2[0]) / 2.0
                    y = (p1[1] + p2[1]) / 2.0
                    events.append(BuildGestureEvent(BuildGesture.PINCH_START, x=x, y=y))
                    self._single_pinched = True
            else:
                raw_ratio = span / max(0.02, self._two_hand_baseline)
                if abs(raw_ratio - 1.0) >= self.scale_deadzone:
                    minimum = 1.0 / self.max_scale_step
                    ratio = self._clamp(raw_ratio, minimum, self.max_scale_step)
                    events.append(BuildGestureEvent(BuildGesture.SCALE, value=ratio))
                    self._two_hand_baseline = span
            self._last_middle_x = None
            self._last_palm_angle = None
            self._middle_pinched = False
            return events

        self._two_hand_baseline = None
        hand = valid[0]
        index_pinch = index_pinches[0]
        middle_distance = _distance(hand[4], hand[12])
        middle_pinch = self._middle_pinch_state(middle_distance)

        if middle_pinch and not index_pinch:
            self._last_palm_angle = None
            self._release_single_pinch(events)
            x, _ = self._smooth_workspace_point(0, 12, hand[12])
            if self._last_middle_x is not None:
                delta = (x - self._last_middle_x) * self.rotation_gain
                if abs(delta) >= 1.0:
                    delta = self._clamp(
                        delta,
                        -self.max_rotation_step,
                        self.max_rotation_step,
                    )
                    events.append(BuildGestureEvent(BuildGesture.ROTATE, value=delta))
            self._last_middle_x = x
            return events

        self._last_middle_x = None

        if index_pinch:
            x, y = self._smooth_workspace_point(0, 8, hand[8])
            angle = _palm_angle(hand, self.mirror_x)
            if not self._single_pinched:
                events.append(BuildGestureEvent(BuildGesture.PINCH_START, x=x, y=y))
                self._single_pinched = True
            else:
                events.append(BuildGestureEvent(BuildGesture.PINCH_MOVE, x=x, y=y))
                if angle is not None and self._last_palm_angle is not None:
                    delta = (angle - self._last_palm_angle + 180.0) % 360.0 - 180.0
                    if abs(delta) >= 4.0:
                        events.append(BuildGestureEvent(
                            BuildGesture.ROTATE,
                            value=self._clamp(
                                delta,
                                -self.max_rotation_step,
                                self.max_rotation_step,
                            ),
                        ))
            self._last_palm_angle = angle
        else:
            self._last_palm_angle = None
            if self._single_pinched:
                self._release_single_pinch(events)

        return events


class GestureTrackingUnavailable(RuntimeError):
    pass


class WebcamGestureTracker:
    """Optional local webcam + MediaPipe loop. No frames are persisted."""

    def __init__(
        self,
        on_event: Callable[[BuildGestureEvent], None],
        *,
        camera_index: int = 0,
        interpreter: GestureInterpreter | None = None,
    ):
        self.on_event = on_event
        self.camera_index = int(camera_index)
        self.interpreter = interpreter or GestureInterpreter()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: str | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    @property
    def error(self) -> str | None:
        return self._error

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name="scorpion-build-gestures", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._thread = None

    @staticmethod
    def _landmarks(hand_landmarks):
        points = getattr(hand_landmarks, "landmark", hand_landmarks)
        return [(float(point.x), float(point.y)) for point in points]

    def _run(self) -> None:
        cap = None
        hands = None
        try:
            import cv2
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision

            if not hasattr(vision, "HandLandmarker"):
                raise GestureTrackingUnavailable("MediaPipe HandLandmarker API ist nicht verfügbar.")

            model_path = ensure_hand_model()
            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                raise GestureTrackingUnavailable("Webcam konnte für Build Mode nicht geöffnet werden.")

            options = vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=0.55,
                min_hand_presence_confidence=0.55,
                min_tracking_confidence=0.55,
            )
            hands = vision.HandLandmarker.create_from_options(options)
            started = time.monotonic()
            last_timestamp = -1
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.08)
                    continue
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = max(
                    last_timestamp + 1,
                    int((time.monotonic() - started) * 1000),
                )
                last_timestamp = timestamp_ms
                result = hands.detect_for_video(mp_image, timestamp_ms)
                landmarks = [
                    self._landmarks(item)
                    for item in (result.hand_landmarks or [])
                ]
                for event in self.interpreter.update(landmarks):
                    self.on_event(event)
                self._stop.wait(0.012)
        except Exception as exc:
            self._error = str(exc)
        finally:
            try:
                if hands is not None:
                    hands.close()
            except Exception:
                pass
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass



def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Prepare Scorpion MK50 gesture tracking.")
    parser.add_argument("--download-model", action="store_true")
    args = parser.parse_args(argv)
    if args.download_model:
        path = ensure_hand_model()
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
