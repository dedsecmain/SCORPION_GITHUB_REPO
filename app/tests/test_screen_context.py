import time

from PIL import Image

from scorpion.config import Settings
from scorpion.screen_context import ScreenContextMonitor


class FakeWindowProvider:
    def foreground(self):
        return "notepad.exe", "Scorpion notes"

    def visible_windows(self):
        return (
            ("notepad.exe", "Scorpion notes"),
            ("explorer.exe", "Projects"),
        )


class FakeImageGrabber:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def grab(self):
        self.calls += 1
        if self.fail:
            raise OSError("headless")
        return Image.new("RGB", (8, 8), "black")


def test_metadata_snapshot_contains_foreground_and_visible_windows():
    monitor = ScreenContextMonitor(
        window_provider=FakeWindowProvider(),
        image_grabber=FakeImageGrabber(),
    )
    context = monitor.snapshot_metadata()
    assert context.active_app == "notepad.exe"
    assert context.window_title == "Scorpion notes"
    assert context.visible_windows == (
        ("notepad.exe", "Scorpion notes"),
        ("explorer.exe", "Projects"),
    )
    assert context.captured_at


def test_monitor_does_not_persist_frames_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    grabber = FakeImageGrabber()
    monitor = ScreenContextMonitor(
        window_provider=FakeWindowProvider(),
        image_grabber=grabber,
    )
    frame = monitor.capture_frame()
    assert frame is not None
    assert frame.size == (8, 8)
    assert grabber.calls == 1
    assert list(tmp_path.iterdir()) == []


def test_capture_frame_returns_none_when_desktop_capture_is_unavailable():
    monitor = ScreenContextMonitor(
        window_provider=FakeWindowProvider(),
        image_grabber=FakeImageGrabber(fail=True),
    )
    assert monitor.capture_frame() is None


def test_background_monitor_emits_metadata_and_stops():
    received = []
    monitor = ScreenContextMonitor(
        window_provider=FakeWindowProvider(),
        image_grabber=FakeImageGrabber(),
        interval_ms=10,
    )
    monitor.start(received.append)
    deadline = time.monotonic() + 1.0
    while not received and time.monotonic() < deadline:
        time.sleep(0.01)
    monitor.stop()
    assert received
    assert received[0].active_app == "notepad.exe"
    assert monitor.running is False


def test_screen_context_defaults_are_local_and_enabled(monkeypatch):
    monkeypatch.delenv("SCORPION_SCREEN_CONTEXT_ENABLED", raising=False)
    monkeypatch.delenv("SCORPION_SCREEN_CONTEXT_INTERVAL_MS", raising=False)
    settings = Settings.from_env()
    assert settings.screen_context_enabled is True
    assert settings.screen_context_interval_ms == 1000
