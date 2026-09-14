from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from .screen import image_to_jpeg_bytes


class VisionProviderProtocol(Protocol):
    def available_models(self) -> set[str]: ...

    def respond(
        self,
        user_text: str,
        history=(),
        image_bytes: bytes | None = None,
        *,
        model: str | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class UIElement:
    label: str
    role: str
    bounds: tuple[int, int, int, int]
    confidence: float


@dataclass(frozen=True)
class VisionResult:
    summary: str
    elements: list[UIElement]


def _json_object_from_text(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None

    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_bounds(value) -> tuple[int, int, int, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        return None
    x1, y1, x2, y2 = (int(round(float(item))) for item in value)
    if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _parse_confidence(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return max(0.0, min(1.0, float(value)))


class LocalVision:
    """Structured, local-only screen/image analysis through an installed vision model."""

    def __init__(self, provider: VisionProviderProtocol, *, model: str):
        self.provider = provider
        self.model = model.strip()

    def _availability_error(self) -> VisionResult | None:
        try:
            installed = self.provider.available_models()
        except Exception as exc:
            return VisionResult(
                summary=f"Lokale Bildanalyse nicht verfügbar: Modellstatus konnte nicht geprüft werden ({exc}).",
                elements=[],
            )
        if self.model not in installed:
            return VisionResult(
                summary=(
                    "Lokale Bildanalyse nicht verfügbar: "
                    f"Das Vision-Modell {self.model} ist nicht installiert."
                ),
                elements=[],
            )
        return None

    def analyze(self, image: Image.Image, prompt: str) -> VisionResult:
        unavailable = self._availability_error()
        if unavailable is not None:
            return unavailable

        image_bytes = image_to_jpeg_bytes(image)
        request_text = (
            "Analysiere dieses Bild lokal. Antworte ausschließlich als JSON-Objekt mit diesem Schema: "
            '{"summary":"kurze Beschreibung","elements":['
            '{"label":"sichtbarer Text oder Name","role":"button/menu/input/text/other",'
            '"bounds":[x1,y1,x2,y2],"confidence":0.0}]}. '
            "Bounds sind Pixelkoordinaten relativ zum Bild. Erfinde keine Elemente. "
            f"Aufgabe des Nutzers: {prompt.strip()}"
        )
        try:
            raw = self.provider.respond(
                request_text,
                history=(),
                image_bytes=image_bytes,
                model=self.model,
            ).strip()
        except Exception as exc:
            return VisionResult(
                summary=f"Lokale Bildanalyse nicht verfügbar: {exc}",
                elements=[],
            )

        payload = _json_object_from_text(raw)
        if payload is None:
            return VisionResult(summary=raw or "Keine lokale Bildanalyse erhalten.", elements=[])

        summary = payload.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            summary = "Lokale Bildanalyse abgeschlossen."
        else:
            summary = summary.strip()

        elements: list[UIElement] = []
        raw_elements = payload.get("elements", [])
        if isinstance(raw_elements, list):
            for item in raw_elements:
                if not isinstance(item, dict):
                    continue
                label = item.get("label", "")
                role = item.get("role", "other")
                if not isinstance(label, str) or not isinstance(role, str):
                    continue
                bounds = _parse_bounds(item.get("bounds"))
                if bounds is None:
                    continue
                elements.append(
                    UIElement(
                        label=label.strip(),
                        role=role.strip() or "other",
                        bounds=bounds,
                        confidence=_parse_confidence(item.get("confidence", 0.0)),
                    )
                )

        return VisionResult(summary=summary, elements=elements)

    def analyze_current(self, monitor, prompt: str) -> VisionResult:
        frame = monitor.capture_frame()
        if frame is None:
            return VisionResult(
                summary="Lokale Bildanalyse nicht verfügbar: Bildschirmaufnahme konnte nicht erstellt werden.",
                elements=[],
            )
        return self.analyze(frame, prompt)
