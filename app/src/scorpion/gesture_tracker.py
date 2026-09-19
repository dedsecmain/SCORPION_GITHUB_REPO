from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable

from .build_mode import BuildGesture, BuildGestureEvent


def _distance(a, b) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


class GestureInterpreter:
    """Turns normalized 21-point hand landmarks into stable Build Mode events."""

    def __init__(
        self,
        *,
        pinch_threshold: float = 0.065,
        middle_pinch_threshold: float = 0.055,
        rotation_gain: float = 260.0,
    ):
        self.pinch_threshold = float(pinch_threshold)
        self.middle_pinch_threshold = float(middle_pinch_threshold)
        self.rotation_gain = float(rotation_gain)
        self._single_pinched = False
        self._last_middle_x: float | None = None
        self._two_hand_baseline: float | None = None

    @staticmethod
    def _valid(hand) -> bool:
        return isinstance(hand, (list, tuple)) and len(hand) >= 21

    def update(self, hands) -> list[BuildGestureEvent]:
        valid = [hand for hand in hands if self._valid(hand)][:2]
        events: list[BuildGestureEvent] = []
        if not valid:
            if self._single_pinched:
                events.append(BuildGestureEvent(BuildGesture.PINCH_END))
            self._single_pinched = False
            self._last_middle_x = None
            self._two_hand_baseline = None
            return events

        index_pinches = [
            _distance(hand[4], hand[8]) <= self.pinch_threshold
            for hand in valid
        ]

        if len(valid) >= 2 and all(index_pinches[:2]):
            p1, p2 = valid[0][8], valid[1][8]
            span = max(0.02, _distance(p1, p2))
            if self._two_hand_baseline is None:
                self._two_hand_baseline = span
                if not self._single_pinched:
                    x = (float(p1[0]) + float(p2[0])) / 2.0
                    y = (float(p1[1]) + float(p2[1])) / 2.0
                    events.append(BuildGestureEvent(BuildGesture.PINCH_START, x=x, y=y))
                    self._single_pinched = True
            else:
                ratio = span / max(0.02, self._two_hand_baseline)
                if abs(ratio - 1.0) >= 0.03:
                    events.append(BuildGestureEvent(BuildGesture.SCALE, value=ratio))
                    self._two_hand_baseline = span
            return events

        self._two_hand_baseline = None
        hand = valid[0]
        index_tip = hand[8]
        index_pinch = index_pinches[0]
        middle_pinch = _distance(hand[4], hand[12]) <= self.middle_pinch_threshold

        if middle_pinch and not index_pinch:
            x = float(hand[12][0])
            if self._last_middle_x is not None:
                delta = (x - self._last_middle_x) * self.rotation_gain
                if abs(delta) >= 1.0:
                    events.append(BuildGestureEvent(BuildGesture.ROTATE, value=delta))
            self._last_middle_x = x
            return events
        self._last_middle_x = None

        if index_pinch:
            x, y = float(index_tip[0]), float(index_tip[1])
            if not self._single_pinched:
                events.append(BuildGestureEvent(BuildGesture.PINCH_START, x=x, y=y))
                self._single_pinched = True
            else:
                events.append(BuildGestureEvent(BuildGesture.PINCH_MOVE, x=x, y=y))
        elif self._single_pinched:
            events.append(BuildGestureEvent(BuildGesture.PINCH_END))
            self._single_pinched = False
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
        return [(float(point.x), float(point.y)) for point in hand_landmarks.landmark]

    def _run(self) -> None:
        cap = None
        hands = None
        try:
            import cv2
            import mediapipe as mp

            if not hasattr(mp, "solutions") or not hasattr(mp.solutions, "hands"):
                raise GestureTrackingUnavailable("MediaPipe Hands API ist nicht verfügbar.")

            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                raise GestureTrackingUnavailable("Webcam konnte für Build Mode nicht geöffnet werden.")

            hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                model_complexity=0,
                min_detection_confidence=0.55,
                min_tracking_confidence=0.55,
            )
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.08)
                    continue
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = hands.process(rgb)
                landmarks = [
                    self._landmarks(item)
                    for item in (result.multi_hand_landmarks or [])
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
