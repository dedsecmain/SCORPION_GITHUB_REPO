from scorpion.build_mode import BuildGesture, BuildGestureEvent, BuildModeSession
from scorpion.gesture_tracker import GestureInterpreter


def hand(index=(0.50, 0.50), thumb=(0.52, 0.50), middle=(0.72, 0.50)):
    points = [(0.0, 0.0)] * 21
    points[4] = thumb
    points[8] = index
    points[12] = middle
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


def test_gesture_interpreter_releases_pinch_before_rotation():
    interpreter = GestureInterpreter()
    start = interpreter.update([hand()])
    assert start and start[0].gesture is BuildGesture.PINCH_START
    rotate_hand = hand(index=(0.80, 0.50), thumb=(0.50, 0.50), middle=(0.52, 0.50))
    events = interpreter.update([rotate_hand])
    assert any(event.gesture is BuildGesture.PINCH_END for event in events)


def test_gesture_interpreter_mirrors_camera_x_for_workspace_control():
    interpreter = GestureInterpreter(mirror_x=True)
    events = interpreter.update([hand(index=(0.20, 0.40), thumb=(0.22, 0.40))])
    assert events[0].gesture is BuildGesture.PINCH_START
    assert abs(events[0].x - 0.80) < 0.001
    assert abs(events[0].y - 0.40) < 0.001
