from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib import error, request

from .persona import build_persona


class OllamaOfflineError(RuntimeError):
    pass


class LocalModelMissingError(RuntimeError):
    pass


@dataclass(frozen=True)
class LocalAIStatus:
    state: str
    detail: str


Transport = Callable[[str, str, dict | None, float], dict]


def _urllib_transport(method: str, url: str, payload: dict | None = None, timeout: float = 5.0) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
    except (error.URLError, OSError, TimeoutError) as exc:
        raise OllamaOfflineError(f"Ollama ist nicht erreichbar: {exc}") from exc
    try:
        return json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Ollama hat eine ungültige Antwort geliefert.") from exc


class OllamaLocalAI:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        transport: Transport | None = None,
        history_limit: int = 10,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.transport = transport or _urllib_transport
        self.history_limit = max(0, int(history_limit))
        self.timeout = timeout

    def available_models(self) -> set[str]:
        data = self.transport("GET", f"{self.base_url}/api/tags", None, 3.0)
        return {
            value
            for item in data.get("models", [])
            for value in (item.get("name"), item.get("model"))
            if isinstance(value, str)
        }

    def status(self, model: str | None = None) -> LocalAIStatus:
        try:
            data = self.transport("GET", f"{self.base_url}/api/tags", None, 3.0)
        except (OllamaOfflineError, OSError, error.URLError, TimeoutError) as exc:
            return LocalAIStatus("offline", f"Ollama ist offline oder nicht installiert. {exc}")

        model_names = {
            value
            for item in data.get("models", [])
            for value in (item.get("name"), item.get("model"))
            if isinstance(value, str)
        }
        selected_model = model or self.model
        if selected_model not in model_names:
            return LocalAIStatus(
                "model_missing",
                f"Lokales Modell fehlt. Führe aus: ollama pull {selected_model}",
            )
        return LocalAIStatus("ready", f"OLLAMA READY · {selected_model}")

    def _require_ready(self, model: str | None = None) -> None:
        status = self.status(model)
        if status.state == "offline":
            raise OllamaOfflineError(status.detail)
        if status.state == "model_missing":
            raise LocalModelMissingError(status.detail)

    def respond(
        self,
        user_text: str,
        history: Iterable[dict[str, str]] = (),
        image_bytes: bytes | None = None,
        *,
        model: str | None = None,
    ) -> str:
        selected_model = model or self.model
        self._require_ready(selected_model)
        recent = list(history)[-self.history_limit :] if self.history_limit else []
        messages: list[dict] = [{"role": "system", "content": build_persona(user_text)}]
        for item in recent:
            role = item.get("role", "user")
            content = item.get("content", "")
            if role in {"user", "assistant", "system"} and isinstance(content, str):
                messages.append({"role": role, "content": content})

        user_message: dict = {"role": "user", "content": user_text}
        if image_bytes is not None:
            user_message["images"] = [base64.b64encode(image_bytes).decode("ascii")]
        messages.append(user_message)

        payload = {"model": selected_model, "messages": messages, "stream": False}
        try:
            data = self.transport("POST", f"{self.base_url}/api/chat", payload, self.timeout)
        except (OllamaOfflineError, OSError, error.URLError, TimeoutError) as exc:
            raise OllamaOfflineError(f"Ollama-Verbindung ist während der Anfrage abgebrochen: {exc}") from exc
        content = data.get("message", {}).get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama hat keine Textantwort geliefert.")
        return content.strip()
