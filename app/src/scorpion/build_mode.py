from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, replace
from enum import Enum


class BuildGesture(str, Enum):
    PINCH_START = "pinch_start"
    PINCH_MOVE = "pinch_move"
    PINCH_END = "pinch_end"
    SCALE = "scale"
    ROTATE = "rotate"
    HOVER = "hover"


@dataclass(frozen=True)
class BuildGestureEvent:
    gesture: BuildGesture
    x: float | None = None
    y: float | None = None
    value: float | None = None


@dataclass(frozen=True)
class BuildObject:
    id: str
    kind: str
    x: float = 0.5
    y: float = 0.5
    z: float = 0.0
    rotation_y: float = 0.0
    scale: float = 1.0


class BuildModeSession:
    """Deterministic local Build Mode state.

    Gesture input mutates only this virtual workspace. Destructive OS/file actions
    are intentionally outside Build Mode and remain confirmation-gated elsewhere.
    """

    ALLOWED_KINDS = {"cube", "sphere", "panel"}

    def __init__(self, *, select_radius: float = 0.18):
        self.active = False
        self.select_radius = max(0.03, min(0.5, float(select_radius)))
        self._objects: dict[str, BuildObject] = {}
        self.selected_id: str | None = None

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _clamp_scale(value: float) -> float:
        return max(0.2, min(5.0, float(value)))

    def activate(self) -> None:
        self.active = True

    def deactivate(self) -> None:
        self.active = False
        self.selected_id = None

    def add_object(
        self,
        kind: str,
        *,
        x: float = 0.5,
        y: float = 0.5,
        z: float = 0.0,
    ) -> BuildObject:
        normalized = str(kind).strip().lower()
        if normalized not in self.ALLOWED_KINDS:
            raise ValueError(f"Nicht unterstütztes Build-Objekt: {kind}")
        item = BuildObject(
            id=uuid.uuid4().hex,
            kind=normalized,
            x=self._clamp01(x),
            y=self._clamp01(y),
            z=max(-1.0, min(1.0, float(z))),
        )
        self._objects[item.id] = item
        return item

    def get(self, object_id: str) -> BuildObject:
        return self._objects[str(object_id)]

    def objects(self) -> list[BuildObject]:
        return list(self._objects.values())

    def _replace_selected(self, **changes) -> BuildObject | None:
        if not self.selected_id or self.selected_id not in self._objects:
            return None
        current = self._objects[self.selected_id]
        updated = replace(current, **changes)
        self._objects[current.id] = updated
        return updated

    def _select_nearest(self, x: float, y: float) -> str | None:
        if not self._objects:
            return None
        px, py = self._clamp01(x), self._clamp01(y)
        best: tuple[float, str] | None = None
        for item in self._objects.values():
            distance = math.hypot(item.x - px, item.y - py)
            if best is None or distance < best[0]:
                best = (distance, item.id)
        if best is None:
            return None
        selected = self._objects[best[1]]
        hit_radius = self.select_radius * max(1.0, min(2.25, selected.scale))
        if best[0] > hit_radius:
            return None
        return best[1]

    def select_at(self, x: float, y: float) -> BuildObject | None:
        self.selected_id = self._select_nearest(x, y)
        return self._objects.get(self.selected_id) if self.selected_id else None

    def clear_selection(self) -> None:
        self.selected_id = None

    def apply(self, event: BuildGestureEvent) -> BuildObject | None:
        if not self.active:
            return None
        gesture = BuildGesture(event.gesture)

        if gesture is BuildGesture.PINCH_START:
            if event.x is None or event.y is None:
                return None
            return self.select_at(event.x, event.y)

        if gesture is BuildGesture.PINCH_END:
            current = self._objects.get(self.selected_id) if self.selected_id else None
            self.selected_id = None
            return current

        if gesture is BuildGesture.PINCH_MOVE:
            if event.x is None or event.y is None:
                return None
            return self._replace_selected(
                x=self._clamp01(event.x),
                y=self._clamp01(event.y),
            )

        if gesture is BuildGesture.SCALE:
            if event.value is None:
                return None
            current = self._objects.get(self.selected_id) if self.selected_id else None
            if current is None:
                return None
            return self._replace_selected(
                scale=self._clamp_scale(current.scale * float(event.value))
            )

        if gesture is BuildGesture.ROTATE:
            if event.value is None:
                return None
            current = self._objects.get(self.selected_id) if self.selected_id else None
            if current is None:
                return None
            return self._replace_selected(
                rotation_y=(current.rotation_y + float(event.value)) % 360.0
            )

        return self._objects.get(self.selected_id) if self.selected_id else None
