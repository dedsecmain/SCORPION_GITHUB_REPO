from scorpion.ai import image_to_data_url
from scorpion.actions import resolve_windows_action


def test_image_data_url_has_jpeg_prefix():
    result = image_to_data_url(b"abc")
    assert result == "data:image/jpeg;base64,YWJj"


def test_action_resolution_is_whitelisted():
    action = resolve_windows_action("calculator")
    assert action is not None
    assert action[0] == "process"
    assert resolve_windows_action("cmd /c format c:") is None


def test_window_targets_are_whitelisted():
    from scorpion.actions import resolve_window_target

    assert resolve_window_target("browser")
    assert resolve_window_target("powershell -enc bad") is None
