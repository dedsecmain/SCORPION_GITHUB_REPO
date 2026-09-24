from scorpion.build_mode import BuildGesture, BuildGestureEvent, BuildModeSession
from scorpion.gesture_tracker import GestureInterpreter


def hand(
    index=(0.50, 0.50),
    thumb=(0.52, 0.50),
    middle=(0.72, 0.50),
    index_mcp=(0.40, 0.58),
    pinky_mcp=(0.60, 0.58),
):
    points = [(0.0, 0.0)] * 21
    points[4] = thumb
    points[5] = index_mcp
    points[8] = index
    points[12] = middle
    points[17] = pinky_mcp
    return points


def test_pinch_drag_keeps_selected_object_until_release():
    session = BuildModeSession(select_radius=0.20)
    cube = session.add_object("cube", x=0.50, y=0.50)
    session.activate()
    session.apply(BuildGestureEvent(BuildGesture.PINCH_START, x=0.50, y=0.50))
    session.apply(BuildGestureEvent(BuildGesture.PINCH_MOVE, x=0.80, y=0.20))
    assert session.selected_id == cube.id
    assert session.get(cube.id).x == 0.80
    assert session.get(cube.id).y == 0.20
    session.apply(BuildGestureEvent(BuildGesture.PINCH_END))
    assert session.selected_id is None


def test_two_hand_scale_does_not_accidentally_drop_selection():
    session = BuildModeSession(select_radius=0.25)
    cube = session.add_object("cube", x=0.50, y=0.50)
    session.activate()
    session.apply(BuildGestureEvent(BuildGesture.PINCH_START, x=0.50, y=0.50))
    session.apply(BuildGestureEvent(BuildGesture.SCALE, value=1.20))
    assert session.selected_id == cube.id
    assert session.get(cube.id).scale == 1.20


def test_gesture_interpreter_keeps_selection_during_palm_twist_rotation():
    interpreter = GestureInterpreter()
    start = interpreter.update([hand()])
    assert start and start[0].gesture is BuildGesture.PINCH_START

    twisted = hand(
        index=(0.50, 0.50),
        thumb=(0.52, 0.50),
        index_mcp=(0.46, 0.48),
        pinky_mcp=(0.54, 0.68),
    )
    events = interpreter.update([twisted])

    assert not any(event.gesture is BuildGesture.PINCH_END for event in events)
    assert any(event.gesture is BuildGesture.ROTATE for event in events)


def test_short_tracking_dropout_does_not_release_object():
    interpreter = GestureInterpreter(dropout_grace_frames=2)
    assert interpreter.update([hand()])[0].gesture is BuildGesture.PINCH_START
    assert interpreter.update([]) == []
    assert interpreter.update([]) == []
    released = interpreter.update([])
    assert any(event.gesture is BuildGesture.PINCH_END for event in released)


def test_gesture_interpreter_mirrors_camera_x_for_workspace_control():
    interpreter = GestureInterpreter(mirror_x=True)
    events = interpreter.update([hand(index=(0.20, 0.40), thumb=(0.22, 0.40))])
    assert events[0].gesture is BuildGesture.PINCH_START
    assert abs(events[0].x - 0.80) < 0.001
    assert abs(events[0].y - 0.40) < 0.001
