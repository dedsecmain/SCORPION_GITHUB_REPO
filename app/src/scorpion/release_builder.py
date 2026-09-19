from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


UPDATE_ROOT_FILES = (
    "requirements.txt",
    "pyproject.toml",
    "run_scorpion.bat",
    "setup_scorpion.bat",
    "README.md",
)
FULL_EXTRA_FILES = (".env.example",)
_FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class ReleaseBuild:
    update_zip: Path
    full_zip: Path
    manifest_path: Path
    manifest_bytes: bytes


def _safe_release_path(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    normalized = path.as_posix()
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe release path: {value}")
    lowered = normalized.casefold()
    if lowered == ".env" or lowered.startswith((".scorpion/", "data/")):
        raise ValueError(f"protected release path: {value}")
    if lowered.startswith(("memory", "adaptive")) and lowered.endswith(".json"):
        raise ValueError(f"protected release path: {value}")
    if "private" in lowered and "key" in lowered:
        raise ValueError(f"private key path is never packageable: {value}")
    if "signing" in lowered and "key" in lowered:
        raise ValueError(f"signing key path is never packageable: {value}")
    return normalized


def _update_files(app_root: Path) -> list[str]:
    items: list[str] = []
    source = app_root / "src" / "scorpion"
    for path in sorted(source.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}:
            items.append(_safe_release_path(path.relative_to(app_root).as_posix()))
    for name in UPDATE_ROOT_FILES:
        path = app_root / name
        if not path.is_file():
            raise FileNotFoundError(f"required release file missing: {name}")
        items.append(_safe_release_path(name))
    return sorted(dict.fromkeys(items))


def _full_files(app_root: Path, update_files: list[str]) -> list[str]:
    items = list(update_files)
    for name in FULL_EXTRA_FILES:
        path = app_root / name
        if path.is_file():
            items.append(_safe_release_path(name))
    return sorted(dict.fromkeys(items))


def _write_deterministic_zip(path: Path, app_root: Path, files: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for rel in sorted(files):
            data = (app_root / Path(rel)).read_bytes()
            info = zipfile.ZipInfo(rel, date_time=_FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_release(app_root: Path | str, output_dir: Path | str, *, version: str) -> ReleaseBuild:
    app_root = Path(app_root).resolve()
    output_dir = Path(output_dir).resolve()
    version = str(version).strip()
    if not version.startswith("v") or version != "v74.0.0":
        raise ValueError("MK74 release version must be v74.0.0")

    update_files = _update_files(app_root)
    full_files = _full_files(app_root, update_files)
    output_dir.mkdir(parents=True, exist_ok=True)

    update_zip = output_dir / "SCORPION_update.zip"
    full_zip = output_dir / "SCORPION_MK74.zip"
    _write_deterministic_zip(update_zip, app_root, update_files)
    _write_deterministic_zip(full_zip, app_root, full_files)

    file_entries = [
        {
            "path": rel,
            "sha256": _sha256((app_root / Path(rel)).read_bytes()),
        }
        for rel in update_files
    ]
    manifest = {
        "version": version,
        "min_updater": 1,
        "package_sha256": _sha256(update_zip.read_bytes()),
        "files": file_entries,
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_bytes(manifest_bytes)
    return ReleaseBuild(update_zip, full_zip, manifest_path, manifest_bytes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build deterministic Scorpion MK74 release assets.")
    parser.add_argument("--app-root", default=".")
    parser.add_argument("--out", required=True)
    parser.add_argument("--version", default="v74.0.0")
    args = parser.parse_args(argv)
    result = build_release(args.app_root, args.out, version=args.version)
    print(result.manifest_path)
    print(result.update_zip)
    print(result.full_zip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
