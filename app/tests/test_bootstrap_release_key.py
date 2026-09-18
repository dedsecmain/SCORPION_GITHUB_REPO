import base64
import zipfile
from pathlib import Path


CURRENT_RELEASE_KEY = "jhJyK4L4bIR5vX/z1savl6Jo7pc2xcOiJymdz5FxE3g="
LEGACY_PLACEHOLDER_KEY = base64.b64encode(bytes(range(32))).decode("ascii")


def _legacy_updater_source() -> str:
    archive_path = Path(__file__).resolve().parents[2] / "SCORPION_MkIII.zip"
    assert archive_path.is_file(), "Legacy full package is missing from repository."
    with zipfile.ZipFile(archive_path) as archive:
        candidates = [
            name for name in archive.namelist()
            if name.replace("\\", "/").endswith("src/scorpion/updater.py")
        ]
        assert candidates, "Legacy package contains no updater.py."
        return archive.read(candidates[0]).decode("utf-8")


def test_legacy_full_package_uses_known_placeholder_release_key():
    updater = _legacy_updater_source()
    assert 'base64.b64encode(bytes(range(32))).decode("ascii")' in updater
    assert LEGACY_PLACEHOLDER_KEY != CURRENT_RELEASE_KEY


def test_mk22_bootstrap_requires_key_migration():
    """Document the intentional release blocker without weakening verification."""
    updater = _legacy_updater_source()
    assert CURRENT_RELEASE_KEY not in updater
