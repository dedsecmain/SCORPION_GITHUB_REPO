from __future__ import annotations

import queue

from .build_mode import BuildGesture, BuildGestureEvent, BuildModeSession
from .build_mode_3d import (
    Build3DImportError,
    Software3DRenderer,
    load_mesh_asset,
    primitive_asset,
)
from .gesture_tracker import WebcamGestureTracker


class BuildModeWindow:
    """Interactive 3D Build Mode with gesture + mouse fallback."""

    def __init__(
        self,
        parent,
        *,
        theme: dict[str, str],
        on_close=None,
        gestures_enabled: bool = True,
        camera_index: int = 0,
    ):
        import customtkinter as ctk
        import tkinter as tk

        self.ctk = ctk
        self.tk = tk
        self.parent = parent
        self.theme = theme
        self.on_close = on_close
        self.session = BuildModeSession()
        self.session.activate()
        self.renderer = Software3DRenderer()
        self._mesh_assets: dict[str, object] = {}
        self._events: queue.SimpleQueue[BuildGestureEvent] = queue.SimpleQueue()
        self._tracker = WebcamGestureTracker(self._events.put, camera_index=camera_index)
        self._gestures_enabled = bool(gestures_enabled)
        self._mouse_dragging = False
        self._mouse_last_x: float | None = None
        self._camera_dragging = False
        self._camera_last: tuple[float, float] | None = None

        self.window = ctk.CTkToplevel(parent)
        self.window.title("SCORPION · BUILD MODE 3D")
        self.window.geometry("1100x760")
        self.window.minsize(860, 620)
        self.window.configure(fg_color=theme["bg"])
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_rowconfigure(1, weight=1)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        top = ctk.CTkFrame(self.window, fg_color=theme["panel"], corner_radius=0)
        top.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            top,
            text="BUILD MODE · RED HOLO 3D WORKSPACE",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=theme["text"],
        ).pack(side="left", padx=16, pady=12)

        self.status = ctk.CTkLabel(
            top,
            text="3D CORE STARTING",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme["cyan"],
        )
        self.status.pack(side="right", padx=16)

        toolbar = ctk.CTkFrame(self.window, fg_color=theme["panel_alt"], corner_radius=0)
        toolbar.grid(row=2, column=0, sticky="ew")

        for label, kind in (("+ CUBE", "cube"), ("+ SPHERE", "sphere"), ("+ PANEL", "panel")):
            self._button(toolbar, label, lambda k=kind: self.add_object(k), width=100)

        self._button(toolbar, "IMPORT 3D", self.import_3d, width=105, bright=True)
        self._button(toolbar, "GRÖSSE +", lambda: self._scale_selected(1.12), width=90)
        self._button(toolbar, "GRÖSSE −", lambda: self._scale_selected(0.89), width=90)
        self._button(toolbar, "VOR", lambda: self._move_depth(0.12), width=58)
        self._button(toolbar, "ZURÜCK", lambda: self._move_depth(-0.12), width=76)
        self._button(toolbar, "RESET CAM", self._reset_camera, width=92)
        self._button(toolbar, "GESTURES", self.toggle_gestures, width=92)

        ctk.CTkLabel(
            toolbar,
            text="Pinch: bewegen · 2 Hände: Größe · Hand drehen: Objekt · Alt+Rechts: Kamera",
            text_color=theme["muted"],
        ).pack(side="right", padx=14)

        self.canvas = tk.Canvas(
            self.window,
            bg=theme["panel"],
            highlightthickness=1,
            highlightbackground=theme["border_hot"],
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=14, pady=14)
        self.canvas.bind("<ButtonPress-1>", self._mouse_down)
        self.canvas.bind("<B1-Motion>", self._mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._mouse_up)
        self.canvas.bind("<MouseWheel>", self._mouse_wheel)
        self.canvas.bind("<ButtonPress-3>", self._mouse_rotate_start)
        self.canvas.bind("<B3-Motion>", self._mouse_rotate)
        self.canvas.bind("<ButtonRelease-3>", self._mouse_rotate_end)
        self.canvas.bind("<Alt-ButtonPress-3>", self._camera_orbit_start)
        self.canvas.bind("<Alt-B3-Motion>", self._camera_orbit)
        self.canvas.bind("<Alt-ButtonRelease-3>", self._camera_orbit_end)
        self.window.bind("<Escape>", self._clear_selection)

        self.add_object("cube", x=0.36, y=0.48)
        self.add_object("sphere", x=0.64, y=0.48)
        if self._gestures_enabled:
            self._tracker.start()
        else:
            self.status.configure(text="GESTURES OFF", text_color=theme["muted"])

        self.window.after(80, self.render)
        self.window.after(16, self._tick)

    def _button(self, parent, text, command, *, width=100, bright=False):
        return self.ctk.CTkButton(
            parent,
            text=text,
            width=width,
            command=command,
            fg_color=self.theme["cyan_dim"],
            hover_color="#5A0B13",
            border_width=1,
            border_color=self.theme["border_hot"],
            text_color=self.theme["accent_bright"] if bright else self.theme["text"],
        ).pack(side="left", padx=5, pady=10)

    def add_object(self, kind: str, *, x: float = 0.5, y: float = 0.5):
        item = self.session.add_object(kind, x=x, y=y)
        self._mesh_assets[item.id] = primitive_asset(kind)
        self.session.selected_id = item.id
        self.render()
        return item

    def import_3d(self) -> None:
        from tkinter import filedialog

        path = filedialog.askopenfilename(
            parent=self.window,
            title="3D-Objekt in Scorpion importieren",
            filetypes=[
                ("3D Modelle", "*.obj *.glb *.gltf *.stl *.ply"),
                ("Wavefront OBJ", "*.obj"),
                ("glTF Binary", "*.glb"),
                ("glTF", "*.gltf"),
                ("STL", "*.stl"),
                ("PLY", "*.ply"),
            ],
        )
        if not path:
            return

        try:
            asset = load_mesh_asset(path)
        except Build3DImportError as exc:
            self.status.configure(
                text=f"IMPORT FEHLER · {str(exc)[:64]}",
                text_color=self.theme["danger"],
            )
            return

        item = self.session.add_object(
            "mesh",
            x=0.5,
            y=0.48,
            name=asset.name,
            source_path=asset.source_path,
        )
        self._mesh_assets[item.id] = asset
        self.session.selected_id = item.id
        self.status.configure(
            text=f"IMPORTIERT · {asset.name} · {asset.face_count} FACES",
            text_color=self.theme["success"],
        )
        self.render()

    def _norm(self, event) -> tuple[float, float]:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        return event.x / width, event.y / height

    def _select_projected(self, x: float, y: float) -> bool:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        px, py = x * width, y * height
        best = None
        for item in self.session.objects():
            center = self.renderer.project_item_center(item, width, height)
            distance = ((float(center[0]) - px) ** 2 + (float(center[1]) - py) ** 2) ** 0.5
            radius = 58.0 * max(0.7, min(2.2, item.scale))
            if distance <= radius and (best is None or distance < best[0]):
                best = (distance, item.id)
        self.session.selected_id = best[1] if best else None
        return self.session.selected_id is not None

    def _mouse_down(self, event) -> None:
        x, y = self._norm(event)
        self._select_projected(x, y)
        self._mouse_dragging = self.session.selected_id is not None
        self.render()

    def _mouse_move(self, event) -> None:
        if not self._mouse_dragging:
            return
        x, y = self._norm(event)
        self.session.apply(BuildGestureEvent(BuildGesture.PINCH_MOVE, x=x, y=y))
        self.render()

    def _mouse_up(self, _event) -> None:
        self._mouse_dragging = False
        self.render()

    def _move_depth(self, delta: float) -> None:
        if self.session.selected_id is None:
            self.status.configure(
                text="ERST OBJEKT AUSWÄHLEN",
                text_color=self.theme["orange"],
            )
            return
        self.session.move_depth(delta)
        self.render()

    def _scale_selected(self, factor: float) -> None:
        if self.session.selected_id is None:
            self.status.configure(
                text="ERST OBJEKT AUSWÄHLEN",
                text_color=self.theme["orange"],
            )
            return
        self.session.apply(BuildGestureEvent(BuildGesture.SCALE, value=float(factor)))
        self.render()

    def _mouse_wheel(self, event) -> None:
        # Alt+wheel zooms the 3D camera; normal wheel scales the selected object.
        if event.state & 0x0008:
            self.renderer.zoom(0.92 if event.delta > 0 else 1.08)
            self.render()
            return
        if self.session.selected_id is None:
            x, y = self._norm(event)
            self.session.select_at(x, y)
        if self.session.selected_id is None:
            return
        self._scale_selected(1.08 if event.delta > 0 else 0.92)

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

    def _mouse_rotate_end(self, _event) -> None:
        self._mouse_last_x = None

    def _camera_orbit_start(self, event) -> None:
        self._camera_dragging = True
        self._camera_last = (float(event.x), float(event.y))

    def _camera_orbit(self, event) -> None:
        if not self._camera_dragging or self._camera_last is None:
            return
        x, y = float(event.x), float(event.y)
        last_x, last_y = self._camera_last
        self.renderer.orbit(
            yaw_delta=(x - last_x) * 0.35,
            pitch_delta=(y - last_y) * 0.25,
        )
        self._camera_last = (x, y)
        self.render()

    def _camera_orbit_end(self, _event) -> None:
        self._camera_dragging = False
        self._camera_last = None

    def _reset_camera(self) -> None:
        self.renderer.reset_camera()
        self.render()

    def _clear_selection(self, _event=None) -> None:
        self.session.clear_selection()
        self._mouse_dragging = False
        self._mouse_last_x = None
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
            if event.gesture is BuildGesture.PINCH_START and event.x is not None and event.y is not None:
                self._select_projected(event.x, event.y)
            else:
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
            camera = self._tracker.active_camera_index
            suffix = f" · CAM {camera}" if camera is not None else ""
            self.status.configure(
                text=f"3D GESTURES ACTIVE{suffix}",
                text_color=self.theme["success"],
            )
        self.window.after(16, self._tick)

    def render(self) -> None:
        self.canvas.delete("all")
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())

        self.renderer.draw_grid(
            self.canvas,
            width,
            height,
            line_color=self.theme["scanline"],
            axis_color=self.theme["border_hot"],
        )
        self.canvas.create_text(
            18,
            18,
            anchor="nw",
            text="SCORPION 3D BUILD SPACE",
            fill=self.theme["muted"],
            font=("Segoe UI", 10, "bold"),
        )
        self.canvas.create_text(
            width - 18,
            18,
            anchor="ne",
            text="ALT+RECHTS: ORBIT · ALT+RAD: ZOOM",
            fill=self.theme["muted"],
            font=("Segoe UI", 9),
        )

        for item in self.session.objects():
            asset = self._mesh_assets.get(item.id)
            if asset is None and item.kind in {"cube", "sphere", "panel"}:
                asset = primitive_asset(item.kind)
                self._mesh_assets[item.id] = asset
            if asset is None:
                continue

            selected = item.id == self.session.selected_id
            self.renderer.draw_mesh(
                self.canvas,
                asset,
                item,
                width,
                height,
                selected=selected,
                accent=self.theme["accent_bright"],
            )

            projected = self.renderer.project_item_center(item, width, height)
            label = item.name or item.kind.upper()
            self.canvas.create_text(
                projected[0],
                projected[1] + 55 * item.scale,
                text=f"{label} · {item.scale:.2f}x · {item.rotation_y:.0f}°",
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
