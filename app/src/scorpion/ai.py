from __future__ import annotations

import base64
from typing import Iterable

from .persona import build_persona


def image_to_data_url(image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


class ScorpionAI:
    def __init__(self, api_key: str, model: str):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def respond(
        self,
        user_text: str,
        history: Iterable[dict[str, str]] = (),
        image_bytes: bytes | None = None,
    ) -> str:
        input_items: list[dict] = [
            {"role": "developer", "content": build_persona()},
        ]
        for item in history:
            input_items.append({"role": item["role"], "content": item["content"]})

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

        response = self.client.responses.create(model=self.model, input=input_items)
        return response.output_text.strip()
