import hashlib
import json
import zipfile
from pathlib import Path

from scorpion.release_builder import build_release


def _fake_app(root: Path) -> Path:
    app = root / "app"
    (app / "src/scorpion").mkdir(parents=True)
    (app / "src/scorpion/__init__.py").write_text('__version__ = "74.0.0"\n', encoding="utf-8")
    (app / "src/scorpion/core.py").write_text("VALUE = 74\n", encoding="utf-8")
    for name, content in {
        "requirements.txt": "pytest>=8\n",
        "pyproject.toml": "[project]\nname='scorpion'\n",
        "run_scorpion.bat": "@echo off\n",
        "setup_scorpion.bat": "@echo off\n",
        "README.md": "# Scorpion\n",
        ".env.example": "SCORPION_MODE=LOCAL\n",
        ".env": "SECRET=never-package\n",
        "memory.json": '{"secret":"no"}',
    }.items():
        (app / name).write_text(content, encoding="utf-8")
    return app


def test_release_builder_is_deterministic_and_excludes_user_data(tmp_path):
    app = _fake_app(tmp_path)
    first = build_release(app, tmp_path / "one", version="v74.0.0")
    second = build_release(app, tmp_path / "two", version="v74.0.0")

    assert first.manifest_bytes == second.manifest_bytes
    assert first.update_zip.read_bytes() == second.update_zip.read_bytes()

    with zipfile.ZipFile(first.update_zip) as archive:
        names = set(archive.namelist())
    assert ".env" not in names
    assert "memory.json" not in names
    assert ".env.example" not in names
    assert "src/scorpion/core.py" in names

    with zipfile.ZipFile(first.full_zip) as archive:
        full_names = set(archive.namelist())
    assert ".env" not in full_names
    assert "memory.json" not in full_names
    assert ".env.example" in full_names


def test_manifest_hashes_match_update_zip(tmp_path):
    app = _fake_app(tmp_path)
    result = build_release(app, tmp_path / "out", version="v74.0.0")
    manifest = json.loads(result.manifest_bytes)

    assert manifest["version"] == "v74.0.0"
    assert manifest["package_sha256"] == hashlib.sha256(result.update_zip.read_bytes()).hexdigest()

    with zipfile.ZipFile(result.update_zip) as archive:
        for item in manifest["files"]:
            assert hashlib.sha256(archive.read(item["path"])).hexdigest() == item["sha256"]
