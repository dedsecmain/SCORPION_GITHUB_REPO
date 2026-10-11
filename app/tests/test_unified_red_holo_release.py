from pathlib import Path
from zipfile import ZipFile

from scorpion.autostart import ensure_windows_autostart
from scorpion.hud import RED_HOLO_STATE_PALETTE, THEME, VoiceVisualState
from scorpion.release_builder import build_release


def test_red_holo_theme_and_voice_palette_are_active():
    assert THEME["cyan"] == "#FF1F2D"
    assert THEME["border_hot"] == "#B5121B"
    assert VoiceVisualState.SPEAKING in RED_HOLO_STATE_PALETTE


def test_signed_update_includes_hologram_assets(tmp_path):
    app = tmp_path / "app"
    (app / "src/scorpion").mkdir(parents=True)
    (app / "assets").mkdir()
    (app / "src/scorpion/__init__.py").write_text('__version__ = "74.0.3"\n')
    (app / "assets/scorpion_holo_red.jpg").write_bytes(b"test hologram")
    for name in ("requirements.txt", "pyproject.toml", "run_scorpion.bat", "setup_scorpion.bat", "README.md"):
        (app / name).write_text("safe\n", encoding="utf-8")
    release = build_release(app, tmp_path / "dist", version="v74.0.3")
    with ZipFile(release.update_zip) as archive:
        assert "assets/scorpion_holo_red.jpg" in archive.namelist()


def test_windows_autostart_migrates_own_mk50_launcher(tmp_path):
    app = tmp_path / "scorpion"
    app.mkdir()
    (app / "run_scorpion.bat").write_text("@echo off\n", encoding="utf-8")
    startup = tmp_path / "startup"
    startup.mkdir()
    old = startup / "Scorpion MK50.cmd"
    old.write_text('@echo off\nset "PYTHONPATH=C:\\old\\src"\nstart "" /min "pythonw.exe" -m scorpion\n', encoding="utf-8")
    status = ensure_windows_autostart(
        app, startup_dir=startup, platform_name="nt", enabled=True
    )
    assert status.enabled
    assert status.path == startup / "Scorpion.cmd"
    assert status.path.exists()
    assert not old.exists()
    assert str(app) in status.path.read_text(encoding="utf-8")


def test_windows_autostart_preserves_unrelated_legacy_file(tmp_path):
    app = tmp_path / "scorpion"
    app.mkdir()
    (app / "run_scorpion.bat").write_text("@echo off\n", encoding="utf-8")
    startup = tmp_path / "startup"
    startup.mkdir()
    old = startup / "Scorpion MK50.cmd"
    old.write_text("@echo off\necho Custom script\n", encoding="utf-8")
    status = ensure_windows_autostart(
        app, startup_dir=startup, platform_name="nt", enabled=True
    )
    assert status.enabled
    assert old.exists()
