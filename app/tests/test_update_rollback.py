from pathlib import Path

import pytest

from scorpion.update_helper import apply_update


def test_failed_update_rolls_back_core_and_preserves_user_state(tmp_path):
    install = tmp_path / "app"
    staged = tmp_path / "stage"
    (install / "src/scorpion").mkdir(parents=True)
    (staged / "src/scorpion").mkdir(parents=True)

    (install / "src/scorpion/core.py").write_text("old", encoding="utf-8")
    (staged / "src/scorpion/core.py").write_text("new", encoding="utf-8")

    protected = {
        ".env": "OPENAI_API_KEY=keep",
        "memory.json": '{"keep": true}',
        "adaptive.json": '{"keep": true}',
        ".scorpion/state.json": '{"keep": true}',
        "data/local.json": '{"keep": true}',
        "models/cache.bin": "keep",
    }
    for rel, content in protected.items():
        target = install / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    before = {rel: (install / rel).read_bytes() for rel in protected}
    manifest = {"files": [{"path": "src/scorpion/core.py"}]}

    with pytest.raises(RuntimeError, match="forced selfcheck failure"):
        apply_update(
            install,
            staged,
            manifest,
            selfcheck=lambda _root: (_ for _ in ()).throw(RuntimeError("forced selfcheck failure")),
        )

    assert (install / "src/scorpion/core.py").read_text(encoding="utf-8") == "old"
    for rel, expected in before.items():
        assert (install / rel).read_bytes() == expected


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".scorpion/state.json",
        "data/local.json",
        "memory.json",
        "adaptive.json",
    ],
)
def test_update_manifest_cannot_target_user_state(tmp_path, path):
    install = tmp_path / "app"
    staged = tmp_path / "stage"
    install.mkdir()
    staged.mkdir()
    target = staged / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("bad", encoding="utf-8")

    with pytest.raises(ValueError):
        apply_update(
            install,
            staged,
            {"files": [{"path": path}]},
            selfcheck=lambda _root: None,
        )
