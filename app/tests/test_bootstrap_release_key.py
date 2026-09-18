import zipfile
from pathlib import Path


EXPECTED_RELEASE_KEY = "jhJyK4L4bIR5vX/z1savl6Jo7pc2xcOiJymdz5FxE3g="


def test_legacy_full_package_uses_current_release_public_key():
    archive_path = Path(__file__).resolve().parents[2] / "SCORPION_MkIII.zip"
    assert archive_path.is_file(), "Legacy full package is missing from repository."

    with zipfile.ZipFile(archive_path) as archive:
        candidates = [
            name for name in archive.namelist()
            if name.replace("\\", "/").endswith("src/scorpion/updater.py")
        ]
        assert candidates, "Legacy package contains no updater.py."
        updater = archive.read(candidates[0]).decode("utf-8")

    assert EXPECTED_RELEASE_KEY in updater, (
        "Legacy installed updater does not trust the current Scorpion release key. "
        "A signed bootstrap migration is required before MK22 can auto-update safely."
    )
