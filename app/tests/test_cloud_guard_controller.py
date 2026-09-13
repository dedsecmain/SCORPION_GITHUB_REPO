from scorpion.config import Mode
from test_controller import make_controller


def test_local_mode_blocks_cloud_before_approval(tmp_path):
    approvals = []
    controller, _local, cloud, _audio = make_controller(
        tmp_path, mode=Mode.LOCAL, approval=lambda reason: approvals.append(reason) or True
    )

    answer = controller.request_cloud_once("schwere Aufgabe", "frage")

    assert "LOCAL" in answer
    assert approvals == []
    assert cloud.calls == []


def test_denied_cloud_approval_makes_no_cloud_call(tmp_path):
    approvals = []
    controller, _local, cloud, _audio = make_controller(
        tmp_path, mode=Mode.HYBRID, approval=lambda reason: approvals.append(reason) or False
    )

    answer = controller.request_cloud_once("schwere Aufgabe", "frage")

    assert "nicht freigegeben" in answer.lower()
    assert approvals == ["schwere Aufgabe"]
    assert cloud.calls == []


def test_approved_cloud_request_calls_cloud_exactly_once(tmp_path):
    controller, _local, cloud, _audio = make_controller(
        tmp_path, mode=Mode.CLOUD, approval=lambda _reason: True
    )

    answer = controller.request_cloud_once("schwere Aufgabe", "frage")

    assert answer == "cloud answer"
    assert len(cloud.calls) == 1
    assert cloud.calls[0][1] == "frage"


def test_chatgpt_handoff_does_not_call_cloud(tmp_path):
    controller, _local, cloud, _audio = make_controller(tmp_path)

    result = controller.prepare_chatgpt_handoff("frage", image_bytes=b"jpeg")

    assert result.opened is True
    assert "PROMPT:frage:True" in result.prompt
    assert cloud.calls == []
