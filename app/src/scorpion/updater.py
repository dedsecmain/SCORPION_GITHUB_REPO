from __future__ import annotations

import base64
import hashlib
import json
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib import request


class UpdateVerificationError(RuntimeError):
    pass


ALLOWED_UPDATE_PREFIXES = (
    "src/scorpion/",
    "requirements.txt",
    "pyproject.toml",
    "run_scorpion.bat",
    "setup_scorpion.bat",
    "README.md",
)

# Project release-signing public key. Replace only as part of a signed updater migration.
DEFAULT_PUBLIC_KEY_B64 = "jhJyK4L4bIR5vX/z1savl6Jo7pc2xcOiJymdz5FxE3g="


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    notes: str
    manifest_url: str
    signature_url: str
    package_url: str


class GitHubTransport:
    def get_json(self, url: str) -> dict:
        req = request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Scorpion-MK22"})
        with request.urlopen(req, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_bytes(self, url: str) -> bytes:
        req = request.Request(url, headers={"User-Agent": "Scorpion-MK22"})
        with request.urlopen(req, timeout=30) as response:
            return response.read()


def _version_tuple(value: str) -> tuple[int, ...]:
    raw = str(value or "").strip().lower()
    if raw.startswith("v"):
        raw = raw[1:]
    core = raw.split("+", 1)[0].split("-", 1)[0]
    parts: list[int] = []
    for item in core.split("."):
        digits = "".join(ch for ch in item if ch.isdigit())
        parts.append(int(digits or 0))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer_version(candidate: str, current: str) -> bool:
    return _version_tuple(candidate) > _version_tuple(current)


def _safe_update_path(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise UpdateVerificationError(f"Unsicherer Update-Pfad: {value}")
    normalized = path.as_posix()
    if normalized == ".env" or normalized.startswith(".env/"):
        raise UpdateVerificationError(".env darf niemals per Update ersetzt werden.")
    if normalized.startswith(("data/", ".scorpion/", "memory", "adaptive")):
        raise UpdateVerificationError(f"Benutzerdaten sind nicht updatebar: {normalized}")
    allowed = any(
        normalized.startswith(prefix) if prefix.endswith("/") else normalized == prefix
        for prefix in ALLOWED_UPDATE_PREFIXES
    )
    if not allowed:
        raise UpdateVerificationError(f"Pfad liegt außerhalb der Core-Allowlist: {normalized}")
    return normalized


class Updater:
    def __init__(
        self,
        repo: str,
        *,
        transport=None,
        state_path: Path | str | None = None,
        public_key_b64: str = DEFAULT_PUBLIC_KEY_B64,
        min_check_interval: float = 86400.0,
    ):
        self.repo = repo.strip().strip("/")
        self.transport = transport or GitHubTransport()
        self.state_path = Path(state_path or (Path.home() / ".scorpion" / "update_state.json"))
        self.public_key_b64 = public_key_b64
        self.min_check_interval = float(min_check_interval)

    def _load_state(self) -> dict:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_check_time(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps({"last_check": time.time()}), encoding="utf-8")

    def check(self, *, force: bool = False, current_version: str | None = None) -> UpdateInfo | None:
        if not self.repo:
            return None
        state = self._load_state()
        if not force and time.time() - float(state.get("last_check", 0)) < self.min_check_interval:
            return None
        data = self.transport.get_json(f"https://api.github.com/repos/{self.repo}/releases/latest")
        self._save_check_time()
        assets = {
            item.get("name"): item.get("browser_download_url")
            for item in data.get("assets", [])
            if isinstance(item, dict)
        }
        if current_version and not is_newer_version(str(data.get("tag_name") or "0"), current_version):
            return None
        required = ("manifest.json", "manifest.sig", "SCORPION_update.zip")
        if not all(assets.get(name) for name in required):
            raise UpdateVerificationError("GitHub Release enthält nicht alle signierten Update-Dateien.")
        return UpdateInfo(
            version=str(data.get("tag_name") or "unknown"),
            notes=str(data.get("body") or ""),
            manifest_url=assets["manifest.json"],
            signature_url=assets["manifest.sig"],
            package_url=assets["SCORPION_update.zip"],
        )

    def verify_manifest(self, manifest_bytes: bytes, signature_bytes: bytes) -> dict:
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            public_bytes = base64.b64decode(self.public_key_b64, validate=True)
            key = Ed25519PublicKey.from_public_bytes(public_bytes)
            key.verify(signature_bytes, manifest_bytes)
        except Exception as exc:
            raise UpdateVerificationError("Update-Signatur ist ungültig.") from exc
        try:
            manifest = json.loads(manifest_bytes.decode("utf-8"))
        except Exception as exc:
            raise UpdateVerificationError("Update-Manifest ist ungültig.") from exc
        self.validate_manifest(manifest)
        return manifest

    def validate_manifest(self, manifest: dict) -> None:
        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            raise UpdateVerificationError("Manifest enthält keine Core-Dateien.")
        min_updater = int(manifest.get("min_updater", 1))
        if min_updater > 1:
            raise UpdateVerificationError("Dieses Update benötigt einen neueren Updater.")
        for item in files:
            if not isinstance(item, dict):
                raise UpdateVerificationError("Ungültiger Datei-Eintrag im Manifest.")
            _safe_update_path(str(item.get("path", "")))
            digest = str(item.get("sha256", ""))
            if len(digest) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in digest):
                raise UpdateVerificationError("Ungültiger SHA-256 im Manifest.")

    def stage_update(self, info: UpdateInfo, *, confirmed: bool, destination: Path | str) -> tuple[Path, dict]:
        if not confirmed:
            raise PermissionError("Update-Download benötigt deine Bestätigung.")
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)

        manifest_bytes = self.transport.get_bytes(info.manifest_url)
        signature_bytes = self.transport.get_bytes(info.signature_url)
        manifest = self.verify_manifest(manifest_bytes, signature_bytes)
        if str(manifest.get("version") or "") != info.version:
            raise UpdateVerificationError("Manifest-Version passt nicht zum GitHub Release.")
        package = self.transport.get_bytes(info.package_url)
        expected_package = str(manifest.get("package_sha256", ""))
        if len(expected_package) != 64 or hashlib.sha256(package).hexdigest().lower() != expected_package.lower():
            raise UpdateVerificationError("Update-Paket stimmt nicht mit dem signierten SHA-256 überein.")

        zip_path = destination / "SCORPION_update.zip"
        zip_path.write_bytes(package)
        with zipfile.ZipFile(zip_path) as archive:
            names = set(archive.namelist())
            for item in manifest["files"]:
                rel = _safe_update_path(item["path"])
                if rel not in names:
                    raise UpdateVerificationError(f"Update-Datei fehlt im Paket: {rel}")
                data = archive.read(rel)
                if hashlib.sha256(data).hexdigest().lower() != item["sha256"].lower():
                    raise UpdateVerificationError(f"Datei-Hash ungültig: {rel}")
                target = destination / Path(rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        (destination / "manifest.json").write_bytes(manifest_bytes)
        return destination, manifest
