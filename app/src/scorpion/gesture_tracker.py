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


class GestureInterpreter:
    """Turns normalized 21-point hand landmarks into stable Build Mode events."""

    def __init__(
        self,
        *,
        pinch_threshold: float = 0.065,
        pinch_release_threshold: float = 0.085,
        middle_pinch_threshold: float = 0.055,
        middle_release_threshold: float = 0.075,
        rotation_gain: float = 220.0,
        mirror_x: bool = True,
        smoothing: float = 0.42,
        dropout_grace_frames: int = 2,
        move_epsilon: float = 0.005,
    ):
        self.pinch_threshold = float(pinch_threshold)
        self.pinch_release_threshold = max(self.pinch_threshold, float(pinch_release_threshold))
        self.middle_pinch_threshold = float(middle_pinch_threshold)
        self.middle_release_threshold = max(
            self.middle_pinch_threshold,
            float(middle_release_threshold),
        )
        self.rotation_gain = float(rotation_gain)
        self.mirror_x = bool(mirror_x)
        self.smoothing = max(0.0, min(1.0, float(smoothing)))
        self.dropout_grace_frames = max(0, int(dropout_grace_frames))
        self.move_epsilon = max(0.0, float(move_epsilon))
        self._single_pinched = False
        self._rotation_active = False
        self._last_middle_x: float | None = None
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

    def _release_single_pinch(self, events: list[BuildGestureEvent]) -> None:
        if self._single_pinched:
            events.append(BuildGestureEvent(BuildGesture.PINCH_END))
        self._single_pinched = False
        self._rotation_active = False
        self._last_middle_x = None
        self._two_hand_baseline = None
        self._smoothed_point = None
        self._last_emitted_point = None
        self._missing_frames = 0

    def _index_pinched(self, hand) -> bool:
        threshold = self.pinch_release_threshold if self._single_pinched else self.pinch_threshold
        return _distance(hand[4], hand[8]) <= threshold

    def _middle_pinched(self, hand) -> bool:
        threshold = self.middle_release_threshold if self._rotation_active else self.middle_pinch_threshold
        return _distance(hand[4], hand[12]) <= threshold

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
                self._last_middle_x = None
                self._two_hand_baseline = None
                self._smoothed_point = None
            return events

        self._missing_frames = 0
        index_pinches = [self._index_pinched(hand) for hand in valid]

        if len(valid) >= 2 and all(index_pinches[:2]):
            p1, p2 = valid[0][8], valid[1][8]
            span = max(0.02, _distance(p1, p2))
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
                if abs(ratio - 1.0) >= 0.025:
                    events.append(BuildGestureEvent(BuildGesture.SCALE, value=ratio))
                    self._two_hand_baseline = span
            return events

        self._two_hand_baseline = None
        hand = valid[0]
        index_tip = hand[8]
        index_pinch = index_pinches[0]
        middle_pinch = self._middle_pinched(hand)

        if middle_pinch and not index_pinch:
            x, y = self._workspace_point(hand[12])
            if not self._single_pinched:
                events.append(BuildGestureEvent(BuildGesture.PINCH_START, x=x, y=y))
                self._single_pinched = True
            if self._last_middle_x is not None:
                delta = (x - self._last_middle_x) * self.rotation_gain
                if abs(delta) >= 0.8:
                    events.append(BuildGestureEvent(BuildGesture.ROTATE, value=delta))
            self._last_middle_x = x
            self._rotation_active = True
            return events

        if self._rotation_active:
            self._rotation_active = False
            self._last_middle_x = None
            if not index_pinch:
                self._release_single_pinch(events)
                return events

        if index_pinch:
            point = self._smooth_point(self._workspace_point(index_tip))
            if not self._single_pinched:
                events.append(BuildGestureEvent(BuildGesture.PINCH_START, x=point[0], y=point[1]))
                self._single_pinched = True
                self._last_emitted_point = point
            else:
                previous = self._last_emitted_point
                if previous is None or _distance(previous, point) >= self.move_epsilon:
                    events.append(BuildGestureEvent(BuildGesture.PINCH_MOVE, x=point[0], y=point[1]))
                    self._last_emitted_point = point
        elif self._single_pinched:
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
                trial = cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)
                if trial.isOpened():
                    cap = trial
                    self._active_camera_index = index
                    break
                trial.release()
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
