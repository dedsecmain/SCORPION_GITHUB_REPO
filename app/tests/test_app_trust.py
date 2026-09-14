from scorpion.app_trust import AppTrustRegistry


def test_unknown_app_requires_first_use_approval(tmp_path):
    registry = AppTrustRegistry(tmp_path / "apps.json")
    assert registry.is_trusted("notepad.exe") is False
    registry.set_trust("notepad.exe", True)
    assert AppTrustRegistry(tmp_path / "apps.json").is_trusted("notepad.exe") is True


def test_app_ids_are_normalized_case_insensitively(tmp_path):
    registry = AppTrustRegistry(tmp_path / "apps.json")
    registry.set_trust("NOTEPAD.EXE", True)
    assert registry.is_trusted("notepad.exe") is True


def test_trust_can_be_revoked_and_persists(tmp_path):
    path = tmp_path / "apps.json"
    registry = AppTrustRegistry(path)
    registry.set_trust("calc.exe", True)
    registry.set_trust("calc.exe", False)
    assert AppTrustRegistry(path).is_trusted("calc.exe") is False
