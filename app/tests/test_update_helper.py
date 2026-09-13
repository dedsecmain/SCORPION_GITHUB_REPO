from pathlib import Path

import pytest

from scorpion.update_helper import apply_update


def test_apply_update_preserves_env_and_rolls_back_on_selfcheck_failure(tmp_path):
    install = tmp_path / "install"
    staged = tmp_path / "staged"
    install.mkdir(); staged.mkdir()
    (install / "src/scorpion").mkdir(parents=True)
    (staged / "src/scorpion").mkdir(parents=True)
    (install / "src/scorpion/core.py").write_text("old", encoding="utf-8")
    (staged / "src/scorpion/core.py").write_text("new", encoding="utf-8")
    (install / ".env").write_text("SECRET=keep", encoding="utf-8")

    manifest = {"files": [{"path": "src/scorpion/core.py"}]}
    with pytest.raises(RuntimeError, match="selfcheck"):
        apply_update(
            install,
            staged,
            manifest,
            selfcheck=lambda _root: (_ for _ in ()).throw(RuntimeError("selfcheck failed")),
        )

    assert (install / "src/scorpion/core.py").read_text(encoding="utf-8") == "old"
    assert (install / ".env").read_text(encoding="utf-8") == "SECRET=keep"


def test_apply_update_rejects_env_target(tmp_path):
    install = tmp_path / "install"; staged = tmp_path / "staged"
    install.mkdir(); staged.mkdir()
    (staged / ".env").write_text("bad", encoding="utf-8")
    with pytest.raises(ValueError):
        apply_update(install, staged, {"files": [{"path": ".env"}]}, selfcheck=lambda _root: None)
