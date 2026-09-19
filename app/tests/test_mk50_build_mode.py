from pathlib import Path

import pytest

from scorpion.build_mode import BuildGesture, BuildGestureEvent, BuildModeSession
from scorpion.gesture_tracker import GestureInterpreter, ensure_hand_model
from scorpion.autostart import ensure_windows_autostart


def test_build_mode_pinches_select_move_scale_rotate_and_release():
    session = BuildModeSession()
    cube = session.add_object("cube", x=0.50, y=0.50)
    session.activate()

    session.apply(BuildGestureEvent(BuildGesture.PINCH_START, x=0.51, y=0.49))
    assert session.selected_id == cube.id

    session.apply(BuildGestureEvent(BuildGesture.PINCH_MOVE, x=0.80, y=0.20))
    moved = session.get(cube.id)
    assert moved.x == pytest.approx(0.80)
    assert moved.y == pytest.approx(0.20)

    session.apply(BuildGestureEvent(BuildGesture.SCALE, value=1.5))
    assert session.get(cube.id).scale == pytest.approx(1.5)

    session.apply(BuildGestureEvent(BuildGesture.ROTATE, value=35.0))
    assert session.get(cube.id).rotation_y == pytest.approx(35.0)

    session.apply(BuildGestureEvent(BuildGesture.PINCH_END))
    assert session.selected_id is None


def test_build_mode_clamps_transform_values_and_ignores_events_when_off():
    session = BuildModeSession()
    cube = session.add_object("cube", x=0.5, y=0.5)
    session.apply(BuildGestureEvent(BuildGesture.PINCH_START, x=0.5, y=0.5))
    assert session.selected_id is None

    session.activate()
    session.apply(BuildGestureEvent(BuildGesture.PINCH_START, x=0.5, y=0.5))
    session.apply(BuildGestureEvent(BuildGesture.PINCH_MOVE, x=2.0, y=-1.0))
    session.apply(BuildGestureEvent(BuildGesture.SCALE, value=20.0))
    obj = session.get(cube.id)
    assert 0.0 <= obj.x <= 1.0
    assert 0.0 <= obj.y <= 1.0
    assert obj.scale <= 5.0


def _hand(index=(0.5, 0.5), thumb=(0.7, 0.5), middle=(0.65, 0.5), wrist=(0.5, 0.8)):
    pts = [(0.5, 0.5)] * 21
    pts[0] = wrist
    pts[4] = thumb
    pts[8] = index
    pts[12] = middle
    return pts


def test_gesture_interpreter_emits_drag_sequence_for_index_pinch():
    gi = GestureInterpreter()
    open_hand = _hand(index=(0.5, 0.5), thumb=(0.8, 0.5))
    pinched = _hand(index=(0.50, 0.50), thumb=(0.52, 0.50))
    moved = _hand(index=(0.72, 0.30), thumb=(0.74, 0.30))

    assert gi.update([open_hand]) == []
    start = gi.update([pinched])
    assert start[0].gesture is BuildGesture.PINCH_START
    drag = gi.update([moved])
    assert drag[0].gesture is BuildGesture.PINCH_MOVE
    end = gi.update([open_hand])
    assert end[0].gesture is BuildGesture.PINCH_END


def test_gesture_interpreter_two_pinches_emit_scale_ratio():
    gi = GestureInterpreter()
    left1 = _hand(index=(0.30, 0.50), thumb=(0.32, 0.50))
    right1 = _hand(index=(0.70, 0.50), thumb=(0.72, 0.50))
    gi.update([left1, right1])

    left2 = _hand(index=(0.20, 0.50), thumb=(0.22, 0.50))
    right2 = _hand(index=(0.80, 0.50), thumb=(0.82, 0.50))
    events = gi.update([left2, right2])
    scale = [event for event in events if event.gesture is BuildGesture.SCALE]
    assert scale
    assert scale[0].value > 1.0


def test_autostart_writes_idempotent_startup_launcher(tmp_path):
    app_root = tmp_path / "Scorpion"
    app_root.mkdir()
    (app_root / "run_scorpion.bat").write_text("@echo off\n", encoding="utf-8")
    startup = tmp_path / "Startup"

    first = ensure_windows_autostart(
        app_root,
        enabled=True,
        startup_dir=startup,
        platform_name="nt",
    )
    second = ensure_windows_autostart(
        app_root,
        enabled=True,
        startup_dir=startup,
        platform_name="nt",
    )

    assert first.enabled is True
    assert second.changed is False
    launcher = startup / "Scorpion MK50.cmd"
    text = launcher.read_text(encoding="utf-8")
    assert "pythonw.exe" in text
    assert str(app_root) in text


def test_autostart_can_be_disabled_cleanly(tmp_path):
    app_root = tmp_path / "Scorpion"
    app_root.mkdir()
    startup = tmp_path / "Startup"
    ensure_windows_autostart(app_root, enabled=True, startup_dir=startup, platform_name="nt")
    status = ensure_windows_autostart(app_root, enabled=False, startup_dir=startup, platform_name="nt")
    assert status.enabled is False
    assert not (startup / "Scorpion MK50.cmd").exists()



def test_mediapipe_tasks_hand_landmarker_backend_is_available():
    import mediapipe as mp
    from mediapipe.tasks.python import vision

    assert hasattr(mp, "Image")
    assert hasattr(mp, "ImageFormat")
    assert hasattr(vision, "HandLandmarker")
    assert hasattr(vision, "HandLandmarkerOptions")
    assert hasattr(vision, "RunningMode")


def test_hand_landmarker_model_is_cached_atomically(tmp_path):
    target = tmp_path / "models" / "hand_landmarker.task"
    calls = []

    def fake_download(url, filename):
        calls.append(url)
        Path(filename).write_bytes(b"x" * 1_000_001)
        return filename, None

    first = ensure_hand_model(target, download_fn=fake_download)
    second = ensure_hand_model(target, download_fn=fake_download)
    assert first == target
    assert second == target
    assert len(calls) == 1
    assert target.stat().st_size == 1_000_001


def test_middle_finger_pinch_emits_rotation_after_motion():
    gi = GestureInterpreter()
    first = _hand(index=(0.5, 0.4), thumb=(0.50, 0.50), middle=(0.52, 0.50))
    second = _hand(index=(0.5, 0.4), thumb=(0.60, 0.50), middle=(0.62, 0.50))
    gi.update([first])
    events = gi.update([second])
    rotations = [event for event in events if event.gesture is BuildGesture.ROTATE]
    assert rotations
    assert rotations[0].value != 0
