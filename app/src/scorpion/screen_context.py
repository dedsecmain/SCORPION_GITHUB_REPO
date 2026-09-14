from __future__ import annotations

import ctypes
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from PIL import Image


class WindowProviderProtocol(Protocol):
    def foreground(self) -> tuple[str | None, str]: ...

    def visible_windows(self) -> tuple[tuple[str | None, str], ...]: ...


class ImageGrabberProtocol(Protocol):
    def grab(self) -> Image.Image: ...


@dataclass(frozen=True)
class ScreenContext:
    active_app: str | None
    window_title: str
    visible_windows: tuple[tuple[str | None, str], ...]
    captured_at: str


class WindowsWindowProvider:
    """Small Windows metadata provider. It never captures or persists pixels."""

    @staticmethod
    def _title(hwnd) -> str:
        if os.name != "nt":
            return ""
        user32 = ctypes.windll.user32
        length = int(user32.GetWindowTextLengthW(hwnd))
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value.strip()

    @staticmethod
    def _process_name(hwnd) -> str | None:
        if os.name != "nt":
            return None
        try:
            import psutil
            from ctypes import wintypes

            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return None
            return psutil.Process(pid.value).name()
        except Exception:
            return None

    def foreground(self) -> tuple[str | None, str]:
        if os.name != "nt":
            return None, ""
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                return None, ""
            return self._process_name(hwnd), self._title(hwnd)
        except Exception:
            return None, ""

    def visible_windows(self) -> tuple[tuple[str | None, str], ...]:
        if os.name != "nt":
            return ()
        windows: list[tuple[str | None, str]] = []
        user32 = ctypes.windll.user32

        try:
            callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            @callback_type
            def collect(hwnd, _lparam):
                try:
                    if not user32.IsWindowVisible(hwnd):
                        return True
                    title = self._title(hwnd)
                    if title:
                        windows.append((self._process_name(hwnd), title))
                except Exception:
                    pass
                return True

            user32.EnumWindows(collect, 0)
        except Exception:
            return ()
        return tuple(windows)


class PillowImageGrabber:
    def grab(self) -> Image.Image:
        from PIL import ImageGrab

        return ImageGrab.grab(all_screens=True)


class ScreenContextMonitor:
    """Local metadata monitor with ephemeral, opt-in frame capture."""

    def __init__(
        self,
        *,
        window_provider: WindowProviderProtocol | None = None,
        image_grabber: ImageGrabberProtocol | None = None,
        interval_ms: int = 1000,
    ):
        self.window_provider = window_provider or WindowsWindowProvider()
        self.image_grabber = image_grabber or PillowImageGrabber()
        self.interval_ms = max(10, int(interval_ms))
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._latest: ScreenContext | None = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._running

    @property
    def latest(self) -> ScreenContext | None:
        with self._lock:
            return self._latest

    def snapshot_metadata(self) -> ScreenContext:
        try:
            active_app, window_title = self.window_provider.foreground()
        except Exception:
            active_app, window_title = None, ""
        try:
            visible = tuple(self.window_provider.visible_windows())
        except Exception:
            visible = ()
        context = ScreenContext(
            active_app=active_app,
            window_title=window_title or "",
            visible_windows=visible,
            captured_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._latest = context
        return context

    def capture_frame(self) -> Image.Image | None:
        try:
            return self.image_grabber.grab()
        except Exception:
            return None

    def start(self, callback: Callable[[ScreenContext], None]) -> None:
        if self._running:
            return
        self._stop_event.clear()
        self._running = True

        def loop() -> None:
            try:
                while not self._stop_event.is_set():
                    context = self.snapshot_metadata()
                    try:
                        callback(context)
                    except Exception:
                        pass
                    if self._stop_event.wait(self.interval_ms / 1000.0):
                        break
            finally:
                self._running = False

        self._thread = threading.Thread(
            target=loop,
            name="scorpion-screen-context",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(0.25, self.interval_ms / 1000.0 + 0.1))
        self._thread = None
        self._running = False
