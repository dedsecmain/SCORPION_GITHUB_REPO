from __future__ import annotations

import math
import queue

from .build_mode import BuildGesture, BuildGestureEvent, BuildModeSession
from .gesture_tracker import WebcamGestureTracker


class BuildModeWindow:
    """Interactive local Build Mode workspace with gesture + mouse fallback."""

    def __init__(self, parent, *, theme: dict[str, str], on_close=None):
        import customtkinter as ctk
        import tkinter as tk

        self.ctk = ctk
        self.tk = tk
        self.parent = parent
        self.theme = theme
        self.on_close = on_close
        self.session = BuildModeSession()
        self.session.activate()
        self._events: queue.SimpleQueue[BuildGestureEvent] = queue.SimpleQueue()
        self._tracker = WebcamGestureTracker(self._events.put)
        self._mouse_dragging = False
        self._mouse_last_x: float | None = None

        self.window = ctk.CTkToplevel(parent)
        self.window.title("SCORPION MK50 · BUILD MODE")
        self.window.geometry("1000x720")
        self.window.minsize(780, 560)
        self.window.configure(fg_color=theme["bg"])
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(1, weight=1)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        top = ctk.CTkFrame(self.window, fg_color=theme["panel"], corner_radius=0)
        top.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            top,
            text="BUILD MODE · LOCAL GESTURE WORKSPACE",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=theme["text"],
        ).pack(side="left", padx=16, pady=12)

        self.status = ctk.CTkLabel(
            top,
            text="GESTURES STARTING",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme["cyan"],
        )
        self.status.pack(side="right", padx=16)

        toolbar = ctk.CTkFrame(self.window, fg_color=theme["panel_alt"], corner_radius=0)
        toolbar.grid(row=2, column=0, sticky="ew")
        for label, kind in (("+ CUBE", "cube"), ("+ SPHERE", "sphere"), ("+ PANEL", "panel")):
            ctk.CTkButton(
                toolbar,
                text=label,
                width=105,
                command=lambda k=kind: self.add_object(k),
            ).pack(side="left", padx=6, pady=10)
        ctk.CTkButton(
            toolbar,
            text="GESTURES ON/OFF",
            command=self.toggle_gestures,
        ).pack(side="left", padx=6, pady=10)
        ctk.CTkLabel(
            toolbar,
            text="Pinch: greifen/ziehen · Zwei Pinches: skalieren · Daumen+Mittelfinger: drehen · Maus-Fallback aktiv",
            text_color=theme["muted"],
        ).pack(side="right", padx=14)

        self.canvas = tk.Canvas(
            self.window,
            bg=theme["panel"],
            highlightthickness=1,
            highlightbackground=theme["border"],
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=14, pady=14)
        self.canvas.bind("<ButtonPress-1>", self._mouse_down)
        self.canvas.bind("<B1-Motion>", self._mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._mouse_up)
        self.canvas.bind("<MouseWheel>", self._mouse_wheel)
        self.canvas.bind("<ButtonPress-3>", self._mouse_rotate_start)
        self.canvas.bind("<B3-Motion>", self._mouse_rotate)

        self.add_object("cube", x=0.36, y=0.48)
        self.add_object("sphere", x=0.64, y=0.48)
        self._tracker.start()
        self.window.after(16, self._tick)

    def add_object(self, kind: str, *, x: float = 0.5, y: float = 0.5):
        item = self.session.add_object(kind, x=x, y=y)
        self.render()
        return item

    def _norm(self, event) -> tuple[float, float]:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        return event.x / width, event.y / height

    def _mouse_down(self, event) -> None:
        x, y = self._norm(event)
        self.session.apply(BuildGestureEvent(BuildGesture.PINCH_START, x=x, y=y))
        self._mouse_dragging = self.session.selected_id is not None
        self.render()

    def _mouse_move(self, event) -> None:
        if not self._mouse_dragging:
            return
        x, y = self._norm(event)
        self.session.apply(BuildGestureEvent(BuildGesture.PINCH_MOVE, x=x, y=y))
        self.render()

    def _mouse_up(self, _event) -> None:
        self.session.apply(BuildGestureEvent(BuildGesture.PINCH_END))
        self._mouse_dragging = False
        self.render()

    def _mouse_wheel(self, event) -> None:
        if self.session.selected_id is None:
            return
        factor = 1.08 if event.delta > 0 else 0.92
        self.session.apply(BuildGestureEvent(BuildGesture.SCALE, value=factor))
        self.render()

    def _mouse_rotate_start(self, event) -> None:
        x, y = self._norm(event)
        if self.session.selected_id is None:
            self.session.apply(BuildGestureEvent(BuildGesture.PINCH_START, x=x, y=y))
        self._mouse_last_x = float(event.x)
        self.render()

    def _mouse_rotate(self, event) -> None:
        if self.session.selected_id is None or self._mouse_last_x is None:
            return
        delta = float(event.x) - self._mouse_last_x
        self._mouse_last_x = float(event.x)
        self.session.apply(BuildGestureEvent(BuildGesture.ROTATE, value=delta * 0.6))
        self.render()

    def toggle_gestures(self) -> None:
        if self._tracker.running:
            self._tracker.stop()
            self.status.configure(text="GESTURES OFF", text_color=self.theme["muted"])
        else:
            self._tracker.start()
            self.status.configure(text="GESTURES STARTING", text_color=self.theme["cyan"])

    def _drain_events(self) -> bool:
        changed = False
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            self.session.apply(event)
            changed = True
        return changed

    def _tick(self) -> None:
        if not self.window.winfo_exists():
            return
        if self._drain_events():
            self.render()
        if self._tracker.error:
            self.status.configure(
                text=f"GESTURE FALLBACK · {self._tracker.error[:56]}",
                text_color=self.theme["orange"],
            )
        elif self._tracker.running:
            self.status.configure(text="CAMERA GESTURES ACTIVE", text_color=self.theme["success"])
        self.window.after(16, self._tick)

    @staticmethod
    def _rotated_square(cx: float, cy: float, radius: float, degrees: float):
        angle = math.radians(degrees)
        points = []
        for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            x = dx * radius
            y = dy * radius
            rx = x * math.cos(angle) - y * math.sin(angle)
            ry = x * math.sin(angle) + y * math.cos(angle)
            points.extend((cx + rx, cy + ry))
        return points

    def render(self) -> None:
        self.canvas.delete("all")
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        self.canvas.create_text(
            18, 18, anchor="nw",
            text="SCORPION BUILD SPACE",
            fill=self.theme["muted"],
            font=("Segoe UI", 10, "bold"),
        )
        for item in self.session.objects():
            cx, cy = item.x * width, item.y * height
            radius = 42.0 * item.scale
            selected = item.id == self.session.selected_id
            outline = self.theme["success"] if selected else self.theme["cyan"]
            if item.kind == "sphere":
                shape = self.canvas.create_oval(
                    cx-radius, cy-radius, cx+radius, cy+radius,
                    outline=outline, width=4 if selected else 2,
                    fill=self.theme["cyan_dim"],
                )
            elif item.kind == "panel":
                shape = self.canvas.create_rectangle(
                    cx-radius*1.35, cy-radius*0.7, cx+radius*1.35, cy+radius*0.7,
                    outline=outline, width=4 if selected else 2,
                    fill=self.theme["panel_alt"],
                )
            else:
                shape = self.canvas.create_polygon(
                    self._rotated_square(cx, cy, radius, item.rotation_y),
                    outline=outline, width=4 if selected else 2,
                    fill=self.theme["cyan_dim"],
                )
            self.canvas.tag_raise(shape)
            self.canvas.create_text(
                cx, cy + radius + 18,
                text=f"{item.kind.upper()} · {item.scale:.2f}x · {item.rotation_y:.0f}°",
                fill=self.theme["text"] if selected else self.theme["muted"],
                font=("Segoe UI", 9, "bold"),
            )

    def close(self) -> None:
        self._tracker.stop()
        self.session.deactivate()
        try:
            self.window.destroy()
        finally:
            if callable(self.on_close):
                self.on_close()
