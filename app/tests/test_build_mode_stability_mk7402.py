from scorpion.build_mode import BuildGesture
from scorpion.gesture_tracker import GestureInterpreter


def hand(index=(0.50, 0.50), thumb=(0.52, 0.50), middle=(0.75, 0.50)):
    pts = [(0.0, 0.0)] * 21
    pts[4] = thumb
    pts[8] = index
    pts[12] = middle
    return pts


def gestures(events):
    return [event.gesture for event in events]


def test_pinch_hysteresis_prevents_chatter_near_threshold():
    gi = GestureInterpreter(
        pinch_threshold=0.065,
        pinch_release_threshold=0.085,
        smoothing=1.0,
    )
    start = gi.update([hand(index=(0.50, 0.50), thumb=(0.56, 0.50))])
    assert BuildGesture.PINCH_START in gestures(start)

    # Slightly above engage threshold, still below release threshold.
    noisy = gi.update([hand(index=(0.50, 0.50), thumb=(0.575, 0.50))])
    assert BuildGesture.PINCH_END not in gestures(noisy)
    assert BuildGesture.PINCH_MOVE in gestures(noisy)

    released = gi.update([hand(index=(0.50, 0.50), thumb=(0.60, 0.50))])
    assert BuildGesture.PINCH_END in gestures(released)


def test_single_missing_frame_does_not_drop_selected_object():
    gi = GestureInterpreter(dropout_grace_frames=2, smoothing=1.0)
    gi.update([hand()])
    assert gi.update([]) == []
    events = gi.update([hand(index=(0.65, 0.40), thumb=(0.67, 0.40))])
    assert BuildGesture.PINCH_END not in gestures(events)
    assert BuildGesture.PINCH_MOVE in gestures(events)


def test_smoothing_reduces_small_landmark_jitter():
    gi = GestureInterpreter(smoothing=0.25)
    start = gi.update([hand(index=(0.50, 0.50), thumb=(0.52, 0.50))])[0]
    moved = gi.update([hand(index=(0.70, 0.30), thumb=(0.72, 0.30))])[0]
    assert moved.gesture is BuildGesture.PINCH_MOVE
    # Mirrored workspace X: raw jump would be 0.50 -> 0.30.
    assert 0.30 < moved.x < 0.50
    assert 0.30 < moved.y < 0.50


def test_rotation_delta_is_clamped_against_tracking_spikes():
    gi = GestureInterpreter(rotation_gain=300.0, max_rotation_step=12.0, smoothing=1.0)
    first = hand(index=(0.80, 0.40), thumb=(0.50, 0.50), middle=(0.52, 0.50))
    second = hand(index=(0.80, 0.40), thumb=(0.85, 0.50), middle=(0.87, 0.50))
    gi.update([first])
    events = gi.update([second])
    rotations = [e for e in events if e.gesture is BuildGesture.ROTATE]
    assert rotations
    assert abs(rotations[0].value) <= 12.0


def test_scale_ratio_is_clamped_against_two_hand_tracking_spikes():
    gi = GestureInterpreter(max_scale_step=1.12, smoothing=1.0)
    left = hand(index=(0.35, 0.50), thumb=(0.37, 0.50))
    right = hand(index=(0.65, 0.50), thumb=(0.67, 0.50))
    gi.update([left, right])

    left_far = hand(index=(0.05, 0.50), thumb=(0.07, 0.50))
    right_far = hand(index=(0.95, 0.50), thumb=(0.97, 0.50))
    events = gi.update([left_far, right_far])
    scales = [e for e in events if e.gesture is BuildGesture.SCALE]
    assert scales
    assert scales[0].value <= 1.12
