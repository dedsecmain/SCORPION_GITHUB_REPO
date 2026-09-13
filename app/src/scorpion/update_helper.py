from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath


_ALLOWED_PREFIXES = (
    "src/scorpion/",
    "requirements.txt",
    "pyproject.toml",
    "run_scorpion.bat",
    "setup_scorpion.bat",
    "README.md",
)


def _safe_path(value: str) -> str:
    path = PurePosixPath(str(value).replace("\\", "/"))
    normalized = path.as_posix()
    if path.is_absolute() or ".." in path.parts or normalized == ".env":
        raise ValueError(f"Unsicherer Update-Pfad: {value}")
    allowed = any(
        normalized.startswith(prefix) if prefix.endswith("/") else normalized == prefix
        for prefix in _ALLOWED_PREFIXES
    )
    if not allowed:
        raise ValueError(f"Update-Pfad nicht erlaubt: {value}")
    return normalized


def _default_selfcheck(root: Path) -> None:
    env = os.environ.copy()
    src = str(root / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    result = subprocess.run(
        [sys.executable, "-m", "scorpion.selfcheck"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"selfcheck failed: {result.stderr or result.stdout}")


def apply_update(install_root: Path | str, staged_root: Path | str, manifest: dict, *, selfcheck=None) -> Path:
    install_root = Path(install_root)
    staged_root = Path(staged_root)
    checker = selfcheck or _default_selfcheck
    files = [_safe_path(item["path"]) for item in manifest.get("files", [])]
    if not files:
        raise ValueError("Manifest enthält keine Update-Dateien.")

    backup = Path(tempfile.mkdtemp(prefix="scorpion_backup_"))
    existed: set[str] = set()
    try:
        for rel in files:
            current = install_root / Path(rel)
            if current.exists():
                existed.add(rel)
                backup_target = backup / Path(rel)
                backup_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(current, backup_target)

        for rel in files:
            staged = staged_root / Path(rel)
            if not staged.is_file():
                raise FileNotFoundError(f"Staged update file missing: {rel}")
            target = install_root / Path(rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged, target)

        checker(install_root)
        return backup
    except Exception:
        for rel in files:
            target = install_root / Path(rel)
            saved = backup / Path(rel)
            if rel in existed and saved.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(saved, target)
            elif rel not in existed and target.exists():
                target.unlink()
        raise
