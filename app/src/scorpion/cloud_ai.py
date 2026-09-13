from __future__ import annotations

from typing import Callable, Iterable

from .ai import image_to_data_url
from .cloud_gate import ApprovalToken, CloudApprovalError, CloudGate
from .persona import build_persona


class CloudUnavailableError(RuntimeError):
    pass


class CloudAI:
    def __init__(
        self,
        gate: CloudGate,
        api_key: str | None,
        model: str,
        *,
        client_factory: Callable[[str], object] | None = None,
        history_limit: int = 10,
    ):
        self.gate = gate
        self.api_key = api_key
        self.model = model
        self.client_factory = client_factory or self._default_client_factory
        self.history_limit = max(0, int(history_limit))

    @staticmethod
    def _default_client_factory(api_key: str):
        from openai import OpenAI

        return OpenAI(api_key=api_key)

    def respond(
        self,
        token: ApprovalToken | None,
        user_text: str,
        history: Iterable[dict[str, str]] = (),
        image_bytes: bytes | None = None,
    ) -> str:
        if token is None:
            raise CloudApprovalError("Für diese OpenAI-Anfrage fehlt deine Einmal-Bestätigung.")
        self.gate.consume(token)
        if not self.api_key:
            raise CloudUnavailableError(
                "OPENAI_API_KEY fehlt. Es wurde keine API-Anfrage gesendet und die Freigabe ist verbraucht."
            )

        input_items: list[dict] = [{"role": "developer", "content": build_persona()}]
        recent = list(history)[-self.history_limit :] if self.history_limit else []
        for item in recent:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                input_items.append({"role": role, "content": content})

        if image_bytes is None:
            input_items.append({"role": "user", "content": user_text})
        else:
            input_items.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_text},
                        {"type": "input_image", "image_url": image_to_data_url(image_bytes)},
                    ],
                }
            )

        client = self.client_factory(self.api_key)
        response = client.responses.create(model=self.model, input=input_items)
        text = getattr(response, "output_text", "")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("OpenAI hat keine Textantwort geliefert.")
        return text.strip()
