import json

from PIL import Image

from scorpion.local_vision import LocalVision


class FakeVisionProvider:
    def __init__(self, response, installed=("gemma3:4b",)):
        self.response = response
        self.installed = set(installed)
        self.calls = []

    def available_models(self):
        return set(self.installed)

    def respond(self, prompt, history=(), image_bytes=None, *, model=None):
        self.calls.append(
            {
                "prompt": prompt,
                "history": list(history),
                "image_bytes": image_bytes,
                "model": model,
            }
        )
        return self.response


def test_local_vision_parses_ui_elements_deterministically():
    response = json.dumps(
        {
            "summary": "Editor mit Speichern-Schaltfläche",
            "elements": [
                {
                    "label": "Speichern",
                    "role": "button",
                    "bounds": [10, 20, 90, 50],
                    "confidence": 0.92,
                },
                {
                    "label": "Datei",
                    "role": "menu",
                    "bounds": [0, 0, 60, 18],
                    "confidence": 1.4,
                },
            ],
        }
    )
    provider = FakeVisionProvider(response)
    vision = LocalVision(provider, model="gemma3:4b")

    result = vision.analyze(Image.new("RGB", (120, 80), "white"), "Was ist sichtbar?")

    assert result.summary == "Editor mit Speichern-Schaltfläche"
    assert [item.label for item in result.elements] == ["Speichern", "Datei"]
    assert result.elements[0].bounds == (10, 20, 90, 50)
    assert result.elements[0].confidence == 0.92
    assert result.elements[1].confidence == 1.0
    assert provider.calls[0]["model"] == "gemma3:4b"
    assert provider.calls[0]["image_bytes"]


def test_malformed_coordinates_are_rejected_without_losing_valid_elements():
    response = json.dumps(
        {
            "summary": "UI",
            "elements": [
                {
                    "label": "Bad",
                    "role": "button",
                    "bounds": [50, 20, 10, 40],
                    "confidence": 0.9,
                },
                {
                    "label": "Good",
                    "role": "button",
                    "bounds": [1, 2, 20, 30],
                    "confidence": -2,
                },
            ],
        }
    )
    result = LocalVision(FakeVisionProvider(response), model="gemma3:4b").analyze(
        Image.new("RGB", (64, 64)),
        "UI lesen",
    )
    assert [item.label for item in result.elements] == ["Good"]
    assert result.elements[0].confidence == 0.0


def test_uninstalled_vision_model_returns_clear_unavailable_result():
    provider = FakeVisionProvider("{}", installed={"qwen3:8b"})
    result = LocalVision(provider, model="gemma3:4b").analyze(
        Image.new("RGB", (16, 16)),
        "Was siehst du?",
    )
    assert result.elements == []
    assert "nicht verfügbar" in result.summary.lower()
    assert "gemma3:4b" in result.summary
    assert provider.calls == []


def test_invalid_model_json_does_not_crash_or_invent_ui_elements():
    provider = FakeVisionProvider("Das ist kein JSON")
    result = LocalVision(provider, model="gemma3:4b").analyze(
        Image.new("RGB", (16, 16)),
        "Was siehst du?",
    )
    assert result.elements == []
    assert result.summary == "Das ist kein JSON"
