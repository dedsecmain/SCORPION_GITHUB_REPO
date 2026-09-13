from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .local_ai import LocalModelMissingError, OllamaOfflineError


class RouteStatus(str, Enum):
    ANSWER = "answer"
    ESCALATION_REQUIRED = "escalation_required"


@dataclass(frozen=True)
class RouteResult:
    status: RouteStatus
    text: str
    image_requires_manual_attachment: bool = False


class AssistantRouter:
    def __init__(self, local_ai):
        self.local_ai = local_ai

    def handle_local(
        self,
        text: str,
        history: Iterable[dict[str, str]] = (),
        image_bytes: bytes | None = None,
        *,
        model: str | None = None,
    ) -> RouteResult:
        try:
            if model is None:
                answer = self.local_ai.respond(text, history=history, image_bytes=image_bytes)
            else:
                try:
                    answer = self.local_ai.respond(text, history=history, image_bytes=image_bytes, model=model)
                except TypeError as exc:
                    if "unexpected keyword argument" not in str(exc):
                        raise
                    answer = self.local_ai.respond(text, history=history, image_bytes=image_bytes)
            return RouteResult(RouteStatus.ANSWER, answer)
        except LocalModelMissingError as exc:
            detail = str(exc)
        except OllamaOfflineError as exc:
            detail = str(exc)
        except Exception as exc:
            detail = f"Lokale KI ist fehlgeschlagen: {exc}"

        message = (
            f"Lokal konnte ich die Aufgabe gerade nicht lösen. {detail}\n\n"
            "Du kannst lokal erneut versuchen, ChatGPT-Handoff verwenden (keine OpenAI-API-Credits), "
            "oder OpenAI einmalig freigeben. Eine direkte OpenAI-Anfrage startet nie ohne deine Bestätigung."
        )
        return RouteResult(
            RouteStatus.ESCALATION_REQUIRED,
            message,
            image_requires_manual_attachment=image_bytes is not None,
        )
