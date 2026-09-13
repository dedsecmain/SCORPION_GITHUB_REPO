import pytest

from scorpion.cloud_ai import CloudAI, CloudUnavailableError
from scorpion.cloud_gate import CloudApprovalError, CloudGate


class FakeResponse:
    output_text = "cloud answer"


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse()


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


def test_cloud_service_refuses_missing_token_before_client_creation():
    created = []
    gate = CloudGate(lambda _reason: True)
    ai = CloudAI(gate, api_key="secret", model="gpt-test", client_factory=lambda key: created.append(key) or FakeClient())

    with pytest.raises(CloudApprovalError):
        ai.respond(None, "hi")

    assert created == []


def test_cloud_token_is_consumed_and_cannot_be_reused():
    fake = FakeClient()
    gate = CloudGate(lambda _reason: True)
    ai = CloudAI(gate, api_key="secret", model="gpt-test", client_factory=lambda _key: fake)
    token = gate.request_approval("one request")
    assert token is not None

    assert ai.respond(token, "hi") == "cloud answer"
    with pytest.raises(CloudApprovalError):
        ai.respond(token, "again")
    assert len(fake.responses.calls) == 1


def test_missing_api_key_consumes_approval_without_network():
    created = []
    gate = CloudGate(lambda _reason: True)
    ai = CloudAI(gate, api_key=None, model="gpt-test", client_factory=lambda key: created.append(key) or FakeClient())
    token = gate.request_approval("one request")
    assert token is not None

    with pytest.raises(CloudUnavailableError):
        ai.respond(token, "hi")
    with pytest.raises(CloudApprovalError):
        gate.consume(token)
    assert created == []


def test_cloud_image_request_uses_responses_image_input():
    fake = FakeClient()
    gate = CloudGate(lambda _reason: True)
    ai = CloudAI(gate, api_key="secret", model="gpt-test", client_factory=lambda _key: fake)
    token = gate.request_approval("vision")
    assert token is not None

    ai.respond(token, "look", image_bytes=b"jpeg")

    content = fake.responses.calls[0]["input"][-1]["content"]
    assert content[0] == {"type": "input_text", "text": "look"}
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/jpeg;base64,")
