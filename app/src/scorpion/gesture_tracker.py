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


def _angle_degrees(a, b) -> float:
    return math.degrees(
        math.atan2(float(b[1]) - float(a[1]), float(b[0]) - float(a[0]))
    )


def _angle_delta(current: float, previous: float) -> float:
    return (float(current) - float(previous) + 180.0) % 360.0 - 180.0


class GestureInterpreter:
    """Turns normalized 21-point hand landmarks into stable Build Mode events.

    Controls:
    - thumb + index pinch: select and move
    - two pinched hands moving apart/together: scale up/down
    - wrist/palm twist while pinching: rotate
    """

    def __init__(
        self,
        *,
        pinch_threshold: float = 0.065,
        pinch_release_threshold: float = 0.085,
        rotation_gain: float = 1.0,
        rotation_threshold_degrees: float = 4.0,
        rotation_translation_limit: float = 0.055,
        mirror_x: bool = True,
        smoothing: float = 0.42,
        dropout_grace_frames: int = 2,
        move_epsilon: float = 0.005,
        scale_deadzone: float = 0.025,
    ):
        self.pinch_threshold = float(pinch_threshold)
        self.pinch_release_threshold = max(self.pinch_threshold, float(pinch_release_threshold))
        self.rotation_gain = float(rotation_gain)
        self.rotation_threshold_degrees = max(0.5, float(rotation_threshold_degrees))
        self.rotation_translation_limit = max(0.005, float(rotation_translation_limit))
        self.mirror_x = bool(mirror_x)
        self.smoothing = max(0.0, min(1.0, float(smoothing)))
        self.dropout_grace_frames = max(0, int(dropout_grace_frames))
        self.move_epsilon = max(0.0, float(move_epsilon))
        self.scale_deadzone = max(0.005, float(scale_deadzone))
        self._single_pinched = False
        self._rotation_active = False
        self._last_hand_angle: float | None = None
        self._two_hand_baseline: float | None = None
        self._smoothed_point: tuple[float, float] | None = None
        self._last_emitted_point: tuple[float, float] | None = None
        self._missing_frames = 0

    @staticmethod
    def _valid(hand) -> bool:
        return isinstance(hand, (list, tuple)) and len(hand) >= 21

    def _workspace_point(self, point) -> tuple[float, float]:
        x, y = float(point[0]), float(point[1])
        return (1.0 - x if self.mirror_x else x), y

    def _smooth_point(self, point: tuple[float, float]) -> tuple[float, float]:
        if self._smoothed_point is None:
            self._smoothed_point = point
            return point
        alpha = self.smoothing
        old_x, old_y = self._smoothed_point
        x = old_x + (point[0] - old_x) * alpha
        y = old_y + (point[1] - old_y) * alpha
        self._smoothed_point = (x, y)
        return self._smoothed_point

    def _palm_angle(self, hand) -> float:
        # Index-MCP -> pinky-MCP gives a stable palm axis. Rotating the hand
        # clockwise/counter-clockwise changes this angle without requiring an
        # artificial finger combination.
        angle = _angle_degrees(hand[5], hand[17])
        return -angle if self.mirror_x else angle

    def _release_single_pinch(self, events: list[BuildGestureEvent]) -> None:
        if self._single_pinched:
            events.append(BuildGestureEvent(BuildGesture.PINCH_END))
        self._single_pinched = False
        self._rotation_active = False
        self._last_hand_angle = None
        self._two_hand_baseline = None
        self._smoothed_point = None
        self._last_emitted_point = None
        self._missing_frames = 0

    def _index_pinched(self, hand) -> bool:
        threshold = self.pinch_release_threshold if self._single_pinched else self.pinch_threshold
        return _distance(hand[4], hand[8]) <= threshold

    def update(self, hands) -> list[BuildGestureEvent]:
        valid = [hand for hand in hands if self._valid(hand)][:2]
        events: list[BuildGestureEvent] = []

        if not valid:
            if self._single_pinched:
                self._missing_frames += 1
                if self._missing_frames <= self.dropout_grace_frames:
                    return events
                self._release_single_pinch(events)
            else:
                self._last_hand_angle = None
                self._two_hand_baseline = None
                self._smoothed_point = None
            return events

        self._missing_frames = 0
        index_pinches = [self._index_pinched(hand) for hand in valid]

        # Two pinched hands form a natural resize gesture. Increasing the hand
        # distance enlarges the object; decreasing it shrinks the object.
        if len(valid) >= 2 and all(index_pinches[:2]):
            p1, p2 = valid[0][8], valid[1][8]
            span = max(0.02, _distance(p1, p2))
            self._rotation_active = False
            self._last_hand_angle = None
            if self._two_hand_baseline is None:
                self._two_hand_baseline = span
                if not self._single_pinched:
                    p1x, p1y = self._workspace_point(p1)
                    p2x, p2y = self._workspace_point(p2)
                    midpoint = self._smooth_point(((p1x + p2x) / 2.0, (p1y + p2y) / 2.0))
                    events.append(
                        BuildGestureEvent(
                            BuildGesture.PINCH_START,
                            x=midpoint[0],
                            y=midpoint[1],
                        )
                    )
                    self._single_pinched = True
                    self._last_emitted_point = midpoint
            else:
                ratio = span / max(0.02, self._two_hand_baseline)
                if abs(ratio - 1.0) >= self.scale_deadzone:
                    # Limit one-frame jumps from hand-tracking noise while still
                    # allowing continuous enlargement and shrinking.
                    ratio = max(0.82, min(1.22, ratio))
                    events.append(BuildGestureEvent(BuildGesture.SCALE, value=ratio))
                    self._two_hand_baseline = span
            return events

        self._two_hand_baseline = None
        hand = valid[0]
        index_tip = hand[8]
        index_pinch = index_pinches[0]

        if index_pinch:
            point = self._smooth_point(self._workspace_point(index_tip))
            palm_angle = self._palm_angle(hand)

            if not self._single_pinched:
                events.append(BuildGestureEvent(BuildGesture.PINCH_START, x=point[0], y=point[1]))
                self._single_pinched = True
                self._last_emitted_point = point
                self._last_hand_angle = palm_angle
                return events

            previous_point = self._last_emitted_point
            movement = _distance(previous_point, point) if previous_point is not None else 0.0
            rotation_delta = (
                _angle_delta(palm_angle, self._last_hand_angle)
                if self._last_hand_angle is not None
                else 0.0
            )

            wants_rotation = (
                abs(rotation_delta) >= self.rotation_threshold_degrees
                and movement <= self.rotation_translation_limit
            )
            if self._rotation_active:
                # Once a deliberate twist starts, keep interpreting small
                # follow-up angle changes as rotation until the pinch ends.
                wants_rotation = abs(rotation_delta) >= 0.8

            if wants_rotation:
                self._rotation_active = True
                events.append(
                    BuildGestureEvent(
                        BuildGesture.ROTATE,
                        value=rotation_delta * self.rotation_gain,
                    )
                )
            else:
                if self._rotation_active and movement > self.rotation_translation_limit * 1.6:
                    self._rotation_active = False
                if not self._rotation_active:
                    if previous_point is None or movement >= self.move_epsilon:
                        events.append(BuildGestureEvent(BuildGesture.PINCH_MOVE, x=point[0], y=point[1]))
                        self._last_emitted_point = point

            self._last_hand_angle = palm_angle
            return events

        if self._single_pinched:
            self._release_single_pinch(events)
        else:
            self._last_hand_angle = None
            self._rotation_active = False
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
        self._active_camera_index: int | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def active_camera_index(self) -> int | None:
        return self._active_camera_index

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
            candidate_indices = [self.camera_index] + [
                index for index in (0, 1, 2) if index != self.camera_index
            ]
            backend = getattr(cv2, "CAP_DSHOW", None) if os.name == "nt" else None
            for index in candidate_indices:
                backend_attempts = (backend, None) if backend is not None else (None,)
                for selected_backend in backend_attempts:
                    trial = (
                        cv2.VideoCapture(index, selected_backend)
                        if selected_backend is not None
                        else cv2.VideoCapture(index)
                    )
                    if trial.isOpened():
                        cap = trial
                        self._active_camera_index = index
                        break
                    trial.release()
                if cap is not None and cap.isOpened():
                    break
            if cap is None or not cap.isOpened():
                raise GestureTrackingUnavailable(
                    "Keine nutzbare Webcam für Build Mode gefunden. Maus-Fallback bleibt aktiv."
                )
            try:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 30)
                if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

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
            failed_reads = 0
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    failed_reads += 1
                    if failed_reads >= 20:
                        raise GestureTrackingUnavailable(
                            "Webcam liefert keine Bilder mehr. Maus-Fallback bleibt aktiv."
                        )
                    time.sleep(0.05)
                    continue
                failed_reads = 0
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
            self._active_camera_index = None



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
